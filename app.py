import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
from gmail_client import GmailClient
from email_parser import OrderEmailParser

# Page configuration
st.set_page_config(
    page_title="Gmail Order Tracker",
    page_icon="📧",
    layout="wide"
)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'gmail_client' not in st.session_state:
        st.session_state.gmail_client = None
    if 'orders_df' not in st.session_state:
        st.session_state.orders_df = None
    if 'processing' not in st.session_state:
        st.session_state.processing = False

def main():
    init_session_state()
    
    st.title("📧 Gmail Order Tracker")
    st.markdown("Extract and display order information from your Gmail emails")
    
    # Sidebar for authentication status
    with st.sidebar:
        st.header("Authentication Status")
        if st.session_state.authenticated:
            st.success("✅ Connected to Gmail")
            if st.button("Disconnect", type="secondary"):
                st.session_state.authenticated = False
                st.session_state.gmail_client = None
                st.session_state.orders_df = None
                st.rerun()
        else:
            st.warning("❌ Not connected to Gmail")
    
    # Main content
    if not st.session_state.authenticated:
        show_authentication_section()
    else:
        show_order_extraction_section()

def show_authentication_section():
    """Display Gmail authentication section"""
    st.header("Connect to Gmail")
    st.markdown("""
    To get started, you need to authenticate with your Gmail account.
    This application requires:
    - Read access to your Gmail emails
    - OAuth2 credentials from Google Cloud Console
    """)
    
    # Check if credentials file exists
    if not os.path.exists('credentials.json'):
        st.error("""
        ❌ **Missing credentials.json file**
        
        Please follow these steps:
        1. Go to [Google Cloud Console](https://console.cloud.google.com/)
        2. Create a new project or select existing one
        3. Enable Gmail API
        4. Create OAuth2 credentials (Desktop application)
        5. Download and save as 'credentials.json' in the app directory
        """)
        return
    
    # Check if we have stored credentials first
    if os.path.exists('token.pickle'):
        try:
            gmail_client = GmailClient()
            if gmail_client.authenticate():
                st.session_state.authenticated = True
                st.session_state.gmail_client = gmail_client
                st.rerun()
        except:
            pass  # Continue with manual auth if auto-auth fails
    
    # Manual authentication section
    gmail_client = GmailClient()
    
    # Check if we need to start authentication
    if 'auth_in_progress' not in st.session_state:
        st.session_state.auth_in_progress = False
    
    if st.button("🔐 Authenticate with Gmail", type="primary") or st.session_state.auth_in_progress:
        st.session_state.auth_in_progress = True
        
        try:
            auth_result = gmail_client.authenticate()
            if auth_result and gmail_client.service:
                st.session_state.authenticated = True
                st.session_state.gmail_client = gmail_client
                st.session_state.auth_in_progress = False
                st.success("✅ Successfully connected to Gmail!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Authentication error: {str(e)}")
            st.session_state.auth_in_progress = False

def show_order_extraction_section():
    """Display order extraction and results section"""
    st.header("Extract Order Information")
    
    # Configuration options
    col1, col2 = st.columns(2)
    with col1:
        days_back = st.slider("Days to look back", min_value=1, max_value=90, value=30)
    with col2:
        max_emails = st.slider("Maximum emails to process", min_value=50, max_value=1000, value=200)
    
    if st.button("🔍 Extract Orders", type="primary", disabled=st.session_state.processing):
        st.write("🔄 Button clicked - starting extraction...")
        try:
            extract_orders(days_back, max_emails)
        except Exception as e:
            st.error(f"❌ Critical error in extraction: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    # Display results
    if st.session_state.orders_df is not None:
        display_orders_table()

def extract_orders(days_back: int, max_emails: int):
    """Extract orders from Gmail emails"""
    st.session_state.processing = True
    
    try:
        # Add initial status message
        st.info("🚀 Starting order extraction process...")
        
        # Check authentication first
        if not st.session_state.gmail_client or not st.session_state.gmail_client.service:
            st.error("❌ Gmail client not properly authenticated. Please reconnect.")
            st.session_state.processing = False
            return
        
        st.info("✅ Authentication verified")
        
        with st.spinner(f"Fetching emails from the past {days_back} days..."):
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            st.info(f"📅 Searching from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
            
            # Fetch emails
            emails = st.session_state.gmail_client.get_emails(
                start_date=start_date,
                end_date=end_date,
                max_results=max_emails
            )
            
            if len(emails) == 0:
                st.warning("⚠️ No emails found matching the search criteria. Try:")
                st.write("• Increasing the number of days to look back")
                st.write("• Checking if you have order emails in your inbox")
                st.write("• Making sure the emails aren't in spam/promotions folders")
                st.session_state.processing = False
                return
            else:
                st.success(f"📧 Found {len(emails)} emails to process")
        
        with st.spinner("Parsing emails for order information..."):
            # Parse emails for order information
            parser = OrderEmailParser()
            orders = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Debug container
            debug_expander = st.expander("🔍 Processing Details", expanded=True)
            
            for i, email in enumerate(emails):
                try:
                    progress = (i + 1) / len(emails)
                    progress_bar.progress(progress)
                    status_text.text(f"Processing email {i + 1}/{len(emails)}: {email.get('subject', 'No subject')[:50]}...")
                    
                    # Debug: Show what we're processing
                    with debug_expander:
                        st.write(f"**Email {i + 1}:** {email.get('subject', 'No subject')}")
                        st.write(f"From: {email.get('sender', 'Unknown')}")
                    
                    order_info = parser.parse_email(email)
                    
                    if order_info:
                        orders.append(order_info)
                        with debug_expander:
                            st.success(f"✅ Found order: {order_info.get('order_id', 'No ID')} from {order_info.get('seller', 'Unknown')}")
                    else:
                        with debug_expander:
                            st.info("ℹ️ No order info extracted from this email")
                            
                except Exception as e:
                    with debug_expander:
                        st.error(f"❌ Error parsing email {i + 1}: {str(e)}")
                    continue
            
            progress_bar.empty()
            status_text.empty()
            
            # Summary
            with debug_expander:
                st.write(f"**Summary:** Processed {len(emails)} emails, found {len(orders)} orders")
            
            if orders:
                # Create DataFrame
                df = pd.DataFrame(orders)
                st.session_state.orders_df = df
                st.success(f"✅ Successfully extracted {len(orders)} orders!")
            else:
                st.warning("⚠️ No order information found in the selected emails")
                st.session_state.orders_df = pd.DataFrame()
    
    except Exception as e:
        st.error(f"❌ Error extracting orders: {str(e)}")
        st.error(f"Error details: {type(e).__name__}")
        import traceback
        st.code(traceback.format_exc())
    
    finally:
        st.session_state.processing = False

def display_orders_table():
    """Display the orders table"""
    st.header("📋 Order Information")
    
    if st.session_state.orders_df.empty:
        st.info("No orders found in the processed emails.")
        return
    
    df = st.session_state.orders_df.copy()
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    with col1:
        sellers = st.multiselect(
            "Filter by Seller",
            options=df['seller'].unique().tolist(),
            default=df['seller'].unique().tolist()
        )
    with col2:
        statuses = st.multiselect(
            "Filter by Status",
            options=df['status'].unique().tolist(),
            default=df['status'].unique().tolist()
        )
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=['delivery_date', 'seller', 'order_id', 'status'],
            index=0
        )
    
    # Apply filters
    if sellers:
        df = df[df['seller'].isin(sellers)]
    if statuses:
        df = df[df['status'].isin(statuses)]
    
    # Sort data
    df = df.sort_values(by=sort_by, ascending=False)
    
    # Display summary statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Orders", len(df))
    with col2:
        st.metric("Unique Sellers", df['seller'].nunique())
    with col3:
        delivered_count = len(df[df['status'].str.contains('Delivered|delivered', na=False)])
        st.metric("Delivered Orders", delivered_count)
    with col4:
        pending_count = len(df[~df['status'].str.contains('Delivered|delivered', na=False)])
        st.metric("Pending Orders", pending_count)
    
    # Display the table with order ID prominently shown
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "order_id": st.column_config.TextColumn("Order ID", width="large", help="Order confirmation or tracking number"),
            "seller": st.column_config.TextColumn("Seller", width="medium"),
            "status": st.column_config.TextColumn("Status", width="medium"),
            "delivery_date": st.column_config.DatetimeColumn("Delivery Date", width="medium"),
            "email_subject": st.column_config.TextColumn("Email Subject", width="large")
        },
        column_order=["order_id", "seller", "status", "delivery_date", "email_subject"]
    )
    
    # Download option
    if not df.empty:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"gmail_orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
