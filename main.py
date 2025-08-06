import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64
import hashlib

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="PRK Home Tuition - Login")
DATE_FORMAT = "%d-%m-%Y"
SUBSCRIPTION_PLANS = {
    "₹1000 for 6 months (With Advance Classes)": 182,
    "₹2000 for 1 year (With Advance Classes)": 365,
    "₹200 for 30 days (Subjects Homework Only)": 30
}
UPI_ID = "9685840429@pnb"
SECURITY_QUESTIONS = ["What is your mother's maiden name?", "What was the name of your first pet?", "What city were you born in?"]

# === UTILITY FUNCTIONS ===
@st.cache_resource
def connect_to_gsheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
        credentials_dict = json.loads(decoded_creds)
        credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google APIs: {e}")
        return None

@st.cache_data(ttl=30)
def load_data(sheet_id):
    try:
        client = connect_to_gsheets()
        if client is None: return pd.DataFrame()
        sheet = client.open_by_key(sheet_id).sheet1
        all_values = sheet.get_all_values()
        if not all_values: return pd.DataFrame()
        return pd.DataFrame(all_values[1:], columns=all_values[0])
    except Exception as e:
        st.error(f"Failed to load data for sheet ID {sheet_id}: {e}")
        return pd.DataFrame()

def save_data(df, sheet_id):
    try:
        client = connect_to_gsheets()
        sheet = client.open_by_key(sheet_id).sheet1
        df_to_save = df.drop(columns=['Row ID'], errors='ignore')
        df_str = df_to_save.fillna("").astype(str)
        sheet.clear()
        sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to save data: {e}")
        return False

def find_user(gmail):
    df_users = load_data(ALL_USERS_SHEET_ID)
    if not df_users.empty and 'Gmail ID' in df_users.columns:
        user_data = df_users[df_users['Gmail ID'] == gmail]
        if not user_data.empty:
            return user_data.iloc[0]
    return None

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text if hashed_text else False

# === SHEET IDs ===
ALL_USERS_SHEET_ID = "18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA"

# === SESSION STATE ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_role = ""
    st.session_state.user_gmail = ""
    st.session_state.page_state = "login"

# === MAIN APP ROUTER ===

if st.session_state.logged_in:
    st.sidebar.success(f"Welcome, {st.session_state.user_name}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    role = st.session_state.user_role
    page_map = {
        "admin": "pages/3_Admin_Dashboard.py",
        "principal": "pages/4_Principal_Dashboard.py",
        "teacher": "pages/2_Teacher_Dashboard.py",
        "student": "pages/1_Student_Dashboard.py"
    }
    if role in page_map:
        st.switch_page(page_map[role])
    else:
        st.error("Invalid role detected. Logging out.")
        st.session_state.clear()
        st.rerun()

else:
    st.sidebar.title("Login / New Registration")
    st.markdown("<style> [data-testid='stSidebarNav'] {display: none;} </style>", unsafe_allow_html=True)

    st.image("Ganesh_logo.png", use_container_width=True)
    
    st.markdown(f"""<div style="text-align: center;"><h2>EPS High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.image("PRK_logo.jpg", use_container_width=True)
    with col2:
        st.image("Excellent_logo.jpg", use_container_width=True)
    st.markdown("---")
    
    option = st.sidebar.radio("Select an option:", ["Login", "New Registration", "Forgot Password"])

    if option == "Login":
        st.header("Login to Your Dashboard")
        with st.form("unified_login_form"):
            login_gmail = st.text_input("Username (Your Gmail ID)").lower().strip()
            login_pwd = st.text_input("PIN (Your Password)", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                load_data.clear()
                user_data = find_user(login_gmail)
                if user_data is not None and check_hashes(login_pwd, user_data.get("Password")):
                    role = user_data.get("Role", "").lower()
                    can_login = False
                    if role == "student":
                        if user_data.get("Payment Confirmed") == "Yes" and datetime.today().date() <= pd.to_datetime(user_data.get("Subscribed Till")).date():
                            can_login = True
                        else:
                            st.error("Subscription expired or not confirmed.")
                    elif role in ["teacher", "admin", "principal"]:
                        if user_data.get("Confirmed") == "Yes":
                            can_login = True
                        else:
                            st.error("Registration is pending admin confirmation.")
                    if can_login:
                        st.session_state.logged_in = True
                        st.session_state.user_name = user_data.get("User Name")
                        st.session_state.user_role = role
                        st.session_state.user_gmail = login_gmail
                        st.rerun()
                else:
                    st.error("Incorrect PIN or Gmail.")

    elif option == "New Registration":
        st.header("✍️ New Registration")
        registration_type = st.radio("Register as:", ["Student", "Teacher"])
        
        if registration_type == "Student":
            plan = st.selectbox("Choose Subscription Plan", list(SUBSCRIPTION_PLANS.keys()))
            with st.form("registration_form"):
                name = st.text_input("Full Name")
                father_name = st.text_input("Father's Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                mobile_number = st.text_input("Mobile Number")
                cls = st.selectbox("Class", [f"{i}th" for i in range(5,13)])
                parent_phonepe = st.text_input("Parent's PhonePe Number")
                pwd = st.text_input("Create Password", type="password")
                confirm_pwd = st.text_input("Confirm Password", type="password")
                security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
                security_a = st.text_input("Your Security Answer").lower().strip()
                submitted = st.form_submit_button("Register")
                
                if submitted:
                    if pwd != confirm_pwd:
                        st.error("Passwords do not match.")
                    elif not all([name, father_name, gmail, mobile_number, cls, pwd, plan, security_q, security_a, parent_phonepe]):
                        st.warning("Please fill in ALL details.")
                    else:
                        df = load_data(ALL_USERS_SHEET_ID)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row_data = {
                                "User Name": name, "Father Name": father_name, "Gmail ID": gmail, 
                                "Mobile Number": mobile_number, "Class": cls, "Password": make_hashes(pwd), 
                                "Subscription Plan": plan, "Security Question": security_q, 
                                "Security Answer": security_a, "Role": "Student", 
                                "Payment Confirmed": "No", "Subscription Date": "", 
                                "Subscribed Till": "", "Parent PhonePe": parent_phonepe
                            }
                            df_new = pd.DataFrame([new_row_data])
                            df = pd.concat([df, df_new], ignore_index=True)
                            if save_data(df, ALL_USERS_SHEET_ID):
                                st.success("Registration successful! Please follow payment instructions.")

            if plan:
                st.info(f"Please pay {plan.split(' ')[0]} to the UPI ID: **{UPI_ID}**")
                st.image("Qr logo.jpg", width=250, caption="Scan QR code to pay")
                whatsapp_link = "https://wa.me/919685840429"
                st.success(f"After payment, send a screenshot with student's name and class to our [Official WhatsApp Support]({whatsapp_link}). Your account will be activated within 24 hours.")

                # This code should be inside the "New Registration" section
        elif registration_type == "Teacher":
            st.subheader("Teacher Registration")
            with st.form("teacher_registration_form"):
                name = st.text_input("Full Name")
                gmail = st.text_input("Gmail ID").lower().strip()
                mobile_number = st.text_input("Mobile Number")
                pwd = st.text_input("Create Password", type="password")
                confirm_pwd = st.text_input("Confirm Password", type="password")
                security_q = st.selectbox("Choose a Security Question", SECURITY_QUESTIONS)
                security_a = st.text_input("Your Security Answer").lower().strip()
                
                submitted = st.form_submit_button("Register Teacher")

                if submitted:
                    if pwd != confirm_pwd:
                        st.error("Passwords do not match.")
                    elif not all([name, gmail, mobile_number, pwd, security_q, security_a]):
                        st.warning("Please fill in all details.")
                    else:
                        df = load_data(ALL_USERS_SHEET_ID)
                        if not df.empty and gmail in df["Gmail ID"].values:
                            st.error("This Gmail is already registered.")
                        else:
                            new_row = {
                                "User Name": name, "Gmail ID": gmail, 
                                "Mobile Number": mobile_number, "Password": make_hashes(pwd), 
                                "Security Question": security_q, "Security Answer": security_a, 
                                "Role": "Teacher", "Confirmed": "No"
                            }
                            df_new = pd.DataFrame([new_row])
                            df = pd.concat([df, df_new], ignore_index=True)
                            if save_data(df, ALL_USERS_SHEET_ID):
                                st.success("Teacher registered! Please wait for admin confirmation.")
                                

    
    elif option == "Forgot Password":
        st.header("🔑 Reset Your Password")
        with st.form("forgot_password_form", clear_on_submit=True):
            gmail_to_reset = st.text_input("Enter your registered Gmail ID").lower().strip()
            user_data = find_user(gmail_to_reset)
            if user_data is not None:
                st.info(f"Security Question: **{user_data.get('Security Question')}**")
            
            security_answer = st.text_input("Your Security Answer").lower().strip()
            new_password = st.text_input("Enter new password", type="password")
            confirm_password = st.text_input("Confirm new password", type="password")
            
            if st.form_submit_button("Reset Password"):
                if not all([gmail_to_reset, security_answer, new_password, confirm_password]):
                    st.warning("Please fill all fields.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                elif user_data is None:
                    st.error("This Gmail ID is not registered.")
                elif security_answer != user_data.get("Security Answer"):
                    st.error("Incorrect security answer.")
                else:
                    client = connect_to_gsheets()
                    sheet = client.open_by_key(ALL_USERS_SHEET_ID).sheet1
                    cell = sheet.find(gmail_to_reset)
                    if cell:
                        header_row = sheet.row_values(1)
                        password_col = header_row.index("Password") + 1
                        sheet.update_cell(cell.row, password_col, make_hashes(new_password))
                        load_data.clear()
                        st.success("Password updated! Please log in.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("<div style='text-align: center;'>© 2025 PRK Home Tuition.<br>All Rights Reserved.</div>", unsafe_allow_html=True)
