import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy import stats
from statsmodels.stats.weightstats import ztest as ztest_func
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.core.files.storage import FileSystemStorage
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from .models import Profile

# Use non-interactive backend for matplotlib
import matplotlib
matplotlib.use('Agg')

class SignupView(APIView):
    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not username or not email or not password:
            return Response({"error": "All fields are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.create_user(username=username, email=email, password=password)
        Profile.objects.create(user=user)
        return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    def post(self, request):
        identifier = request.data.get('username') # This can be username or email
        password = request.data.get('password')
        
        user = None
        # Try to authenticate with username
        user = authenticate(username=identifier, password=password)
        
        # If not authenticated, try with email
        if not user:
            try:
                user_obj = User.objects.get(email=identifier)
                user = authenticate(username=user_obj.username, password=password)
            except (User.DoesNotExist, User.MultipleObjectsReturned):
                pass

        if user:
            profile = Profile.objects.get(user=user)
            return Response({
                "message": "Login successful",
                "user_id": user.id,
                "username": user.username,
                "is_pro": profile.is_pro,
                "is_admin": profile.is_admin
            }, status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class AdminLoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user and Profile.objects.get(user=user).is_admin:
            return Response({
                "message": "Admin Login successful",
                "user_id": user.id,
                "is_admin": True
            }, status=status.HTTP_200_OK)
        return Response({"error": "Invalid admin credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class PurchaseProView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        try:
            user = User.objects.get(id=user_id)
            profile = Profile.objects.get(user=user)
            # Mock payment details check (assume successful if provided)
            payment_type = request.data.get('payment_type') # 'upi' or 'debit'
            details = request.data.get('details')
            if not payment_type or not details:
                return Response({"error": "Payment details required"}, status=status.HTTP_400_BAD_REQUEST)
            
            profile.is_pro = True
            profile.save()
            return Response({"message": "Purchase successful! You are now a Pro member."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class SubscriptionListView(APIView):
    def get(self, request):
        pro_profiles = Profile.objects.filter(is_pro=True)
        data = [{"username": p.user.username, "email": p.user.email} for p in pro_profiles]
        return Response(data, status=status.HTTP_200_OK)

# --- Admin CRUD APIs ---

class AdminUserListView(APIView):
    def get(self, request):
        profiles = Profile.objects.all()
        data = []
        for p in profiles:
            data.append({
                "id": p.user.id,
                "username": p.user.username,
                "email": p.user.email,
                "is_pro": p.is_pro,
                "is_admin": p.is_admin,
                "analysis_count": p.analysis_count
            })
        return Response(data, status=status.HTTP_200_OK)

class AdminUserUpdateView(APIView):
    def put(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            profile = Profile.objects.get(user=user)
            
            username = request.data.get('username')
            email = request.data.get('email')
            password = request.data.get('password')
            is_pro = request.data.get('is_pro')
            is_admin = request.data.get('is_admin')
            
            if username: user.username = username
            if email: user.email = email
            if password: user.set_password(password)
            if is_pro is not None: profile.is_pro = is_pro
            if is_admin is not None: profile.is_admin = is_admin
            
            user.save()
            profile.save()
            
            return Response({"message": "User updated successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class AdminUserDeleteView(APIView):
    def delete(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            user.delete()
            return Response({"message": "User deleted successfully"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

# --- CSV Analysis ---

class CSVUploadAndAnalysisView(APIView):
    parser_classes = (MultiPartParser,)

    def post(self, request, format=None):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "Login required to use the analyzer"}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            user = User.objects.get(id=user_id)
            profile = Profile.objects.get(user=user)
            
            # Check limits
            if not profile.is_pro and profile.analysis_count >= 1:
                return Response({"error": "Analysis limit reached. Purchase Pro for unlimited analysis."}, status=status.HTTP_403_FORBIDDEN)
            
            if 'file' not in request.FILES:
                return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
            
            csv_file = request.FILES['file']
            if not csv_file.name.endswith('.csv'):
                return Response({"error": "File is not a CSV"}, status=status.HTTP_400_BAD_REQUEST)

            # Ensure the backend directory exists for uploads (per user requirement)
            backend_dir = os.path.join(settings.MEDIA_ROOT, 'backend')
            if not os.path.exists(backend_dir):
                os.makedirs(backend_dir)

            # Save the file
            fs = FileSystemStorage(location=backend_dir)
            filename = fs.save(csv_file.name, csv_file)
            file_path = os.path.join(backend_dir, filename)

            try:
                # Perform descriptive analysis using pandas
                df = pd.read_csv(file_path)
                
                analysis_sentences = []
                structured_analysis = []
                analysis_sentences.append(f"Analysis for file: {filename}")
                analysis_sentences.append("-" * 30)

                numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
                
                for column in df.columns:
                    col_info = {"column": column, "text": [], "plot": None}
                    analysis_sentences.append(f"'{column}':")
                    col_info["text"].append(f"'{column}':")
                    
                    if column in numeric_cols:
                        col_data = df[column].dropna()
                        col_mean = col_data.mean()
                        col_std = col_data.std()
                        col_min = col_data.min()
                        col_max = col_data.max()
                        
                        s1 = f"  • The mean of '{column}' is {col_mean:.2f}."
                        s2 = f"  • The standard deviation is {col_std:.2f}."
                        s3 = f"  • The minimum value is {col_min} and the maximum value is {col_max}."
                        
                        analysis_sentences.extend([s1, s2, s3])
                        col_info["text"].extend([s1, s2, s3])
                        
                        # Outlier detection using IQR
                        Q1 = col_data.quantile(0.25)
                        Q3 = col_data.quantile(0.75)
                        IQR = Q3 - Q1
                        lower_bound = Q1 - 1.5 * IQR
                        upper_bound = Q3 + 1.5 * IQR
                        outliers = col_data[(col_data < lower_bound) | (col_data > upper_bound)].tolist()
                        
                        if outliers:
                            outlier_str = ", ".join(map(str, sorted(set(outliers))[:5]))
                            if len(set(outliers)) > 5:
                                outlier_str += "..."
                            s_out = f"  • Found {len(outliers)} outliers: {outlier_str}"
                        else:
                            s_out = f"  • No outliers detected in '{column}'."
                        
                        analysis_sentences.append(s_out)
                        col_info["text"].append(s_out)

                        # Generate Box Plot with dark mode theme
                        plt.style.use('dark_background')
                        fig, ax = plt.subplots(figsize=(8, 4))
                        
                        # Set colors from our theme
                        bg_color = '#1e1e20' # --bg-surface
                        text_color = '#ffffff' # --text-main
                        dim_text = '#a0a0a5' # --text-dim
                        border_color = '#323235' # --border-ui
                        accent_color = '#404045' # --accent-ui
                        
                        fig.patch.set_facecolor(bg_color)
                        ax.set_facecolor(bg_color)
                        
                        # Boxplot styling
                        sns.boxplot(x=col_data, color=accent_color, ax=ax, 
                                    medianprops={'color': text_color},
                                    whiskerprops={'color': dim_text},
                                    capprops={'color': dim_text},
                                    flierprops={'markerfacecolor': dim_text, 'markeredgecolor': dim_text})
                        
                        # Axis and label styling
                        ax.set_title(f'Distribution: {column}', color=text_color, pad=20, fontsize=12)
                        ax.set_xlabel(column, color=dim_text)
                        ax.tick_params(colors=dim_text, which='both')
                        
                        # Spines/Borders
                        for spine in ax.spines.values():
                            spine.set_edgecolor(border_color)
                        
                        # Save plot
                        plot_filename = f"plot_{column}_{os.path.splitext(filename)[0]}.png"
                        plot_path = os.path.join(backend_dir, plot_filename)
                        plt.savefig(plot_path, facecolor=bg_color, bbox_inches='tight', dpi=100)
                        plt.close()
                        
                        plot_url = request.build_absolute_uri(settings.MEDIA_URL + 'backend/' + plot_filename)
                        col_info["plot"] = plot_url
                    else:
                        unique_count = df[column].nunique()
                        s_non = f"  • The column '{column}' is non-numeric and has {unique_count} unique values."
                        analysis_sentences.append(s_non)
                        col_info["text"].append(s_non)
                    
                    analysis_sentences.append("")
                    structured_analysis.append(col_info)

                # Save the analysis to a text file
                analysis_filename = f"analysis_{os.path.splitext(filename)[0]}.txt"
                analysis_file_path = os.path.join(backend_dir, analysis_filename)
                
                with open(analysis_file_path, 'w') as f:
                    f.write("\n".join(analysis_sentences))

                # Increment count
                profile.analysis_count += 1
                profile.save()

                # Provide download links
                download_url = request.build_absolute_uri(settings.MEDIA_URL + 'backend/' + analysis_filename)

                return Response({
                    "message": "File uploaded and analyzed successfully",
                    "original_file": filename,
                    "analysis_file": analysis_filename,
                    "download_url": download_url,
                    "analysis": analysis_sentences,
                    "structured_analysis": structured_analysis
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (User.DoesNotExist, Profile.DoesNotExist):
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)
