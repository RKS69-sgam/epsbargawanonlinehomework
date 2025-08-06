
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
import json
import base64

from google.oauth2.service_account import Credentials

# === CONFIGURATION ===
st.set_page_config(layout="wide", page_title="Admin Dashboard")
DATE_FORMAT = "%d-%m-%Y"
SUBSCRIPTION_PLANS = {
    "₹1000 for 6 months (Advance)": 182,
    "₹2000 for 1 year (Advance)": 365,
    "₹200 for 30 days (Normal)": 30
}

# === AUTHENTICATION & GOOGLE SHEETS SETUP ===
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    decoded_creds = base64.b64decode(st.secrets["google_service"]["base64_credentials"])
    credentials_dict = json.loads(decoded_creds)
    credentials = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    ALL_USERS_SHEET = client.open_by_key("18r78yFIjWr-gol6rQLeKuDPld9Rc1uDN8IQRffw68YA").sheet1
except Exception as e:
    st.error(f"Error connecting to Google APIs or Sheets: {e}")
    st.stop()

# === UTILITY FUNCTIONS ===
@st.cache_data(ttl=60)
def load_data(_sheet):
    all_values = _sheet.get_all_values()
    if not all_values:
        return pd.DataFrame()
    df = pd.DataFrame(all_values[1:], columns=all_values[0])
    df.columns = df.columns.str.strip()
    df['Row ID'] = range(2, len(df) + 2)
    return df

def save_data(df, sheet):
    df_to_save = df.drop(columns=['Row ID'], errors='ignore')
    df_str = df_to_save.fillna("").astype(str)
    sheet.clear()
    sheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
    load_data.clear()

# === SECURITY GATEKEEPER ===
if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "admin":
    st.error("You must be logged in as an Admin to view this page.")
    st.page_link("main.py", label="Go to Login Page")
    st.stop()

# === SIDEBAR LOGOUT ===
st.sidebar.success(f"Welcome, {st.session_state.user_name}")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("main.py")

# === ADMIN DASHBOARD UI ===
st.header("👑 Admin Panel")

# --- Display Public Announcement (Updated) ---
try:
    announcements_df = load_data(ANNOUNCEMENTS_SHEET_ID)
    if not announcements_df.empty:
        today_str = datetime.today().strftime(DATE_FORMAT)
        
        # Filter for announcements with today's date
        todays_announcement = announcements_df[announcements_df.get('Date') == today_str]
        
        if not todays_announcement.empty:
            latest_message = todays_announcement['Message'].iloc[0]
            st.info(f"📢 **Public Announcement:** {latest_message}")
except Exception:
    # Fail silently if announcements can't be loaded
    pass
# ---------------------------------------------


# Load all user data
df_users = load_data(ALL_USERS_SHEET)

# Display user counts
total_students = len(df_users[df_users['Role'] == 'Student'])
total_teachers = len(df_users[df_users['Role'] == 'Teacher'])

col1, col2 = st.columns(2)
col1.metric("Total Registered Students", total_students)
col2.metric("Total Registered Teachers", total_teachers)

st.markdown("---")

tab1, tab2 = st.tabs(["Student Management", "Teacher Management"])

with tab1:
    st.subheader("Manage Student Registrations")
    df_students = df_users[df_users['Role'] == 'Student']
    
    st.markdown("#### Pending Payment Confirmations")
    unconfirmed_students = df_students[df_students.get("Payment Confirmed") != "Yes"]
    if unconfirmed_students.empty:
        st.info("No pending student payments.")
    else:
        for index, row in unconfirmed_students.iterrows():
            st.write(f"**Name:** {row.get('User Name')} | **Plan:** {row.get('Subscription Plan')}")
            if st.button(f"✅ Confirm Payment for {row.get('User Name')}", key=f"confirm_student_{row.get('Gmail ID')}"):
                plan_days = SUBSCRIPTION_PLANS.get(row.get("Subscription Plan"), 30)
                today = datetime.today()
                till_date = (today + timedelta(days=plan_days)).strftime(DATE_FORMAT)
                
                # Find the original index from the main user dataframe to update
                original_index = df_users[df_users['Gmail ID'] == row.get('Gmail ID')].index[0]
                df_users.loc[original_index, "Subscription Date"] = today.strftime(DATE_FORMAT)
                df_users.loc[original_index, "Subscribed Till"] = till_date
                df_users.loc[original_index, "Payment Confirmed"] = "Yes"
                
                save_data(df_users, ALL_USERS_SHEET)
                st.success(f"Payment confirmed for {row.get('User Name')}.")
                st.rerun()

    st.markdown("---")
    st.markdown("#### Confirmed Students")
    confirmed_students = df_students[df_students.get("Payment Confirmed") == "Yes"]
    st.dataframe(confirmed_students)

with tab2:
    st.subheader("Manage Teacher Registrations")
    df_teachers = df_users[df_users['Role'].isin(['Teacher', 'Principal', 'Admin'])]

    st.markdown("#### Pending Teacher Confirmations")
    unconfirmed_teachers = df_teachers[df_teachers.get("Confirmed") != "Yes"]
    if unconfirmed_teachers.empty:
        st.info("No pending teacher confirmations.")
    else:
        for index, row in unconfirmed_teachers.iterrows():
            st.write(f"**Name:** {row.get('User Name')} | **Gmail:** {row.get('Gmail ID')}")
            if st.button(f"✅ Confirm Teacher: {row.get('User Name')}", key=f"confirm_teacher_{row.get('Gmail ID')}"):
                original_index = df_users[df_users['Gmail ID'] == row.get('Gmail ID')].index[0]
                df_users.loc[original_index, "Confirmed"] = "Yes"
                save_data(df_users, ALL_USERS_SHEET)
                st.success(f"Teacher {row.get('User Name')} confirmed.")
                st.rerun()

    st.markdown("---")
    st.markdown("#### Confirmed Teachers")
    confirmed_teachers = df_teachers[df_teachers.get("Confirmed") == "Yes"]
    st.dataframe(confirmed_teachers)
