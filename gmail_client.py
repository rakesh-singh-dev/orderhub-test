import os
import pickle
import base64
import email
from datetime import datetime, timezone
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import streamlit as st

class GmailClient:
    """Gmail API client for fetching and processing emails"""
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self):
        self.service = None
        self.credentials = None
    
    def authenticate(self) -> bool:
        """Authenticate with Gmail API using OAuth2 flow"""
        try:
            creds = None
            
            # Check if token file exists
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception:
                        creds = None
                
                if not creds:
                    if not os.path.exists('credentials.json'):
                        raise FileNotFoundError("credentials.json file not found")
                    
                    # Use manual OAuth flow for cloud environment
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', self.SCOPES)
                    
                    # Set redirect URI for manual flow
                    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
                    
                    # Generate authorization URL
                    auth_url, _ = flow.authorization_url(
                        prompt='consent',
                        access_type='offline'
                    )
                    
                    st.info("**Manual Authentication Required**")
                    st.write("1. Click the link below to authorize the application:")
                    st.markdown(f"[🔗 **Click here to authorize**]({auth_url})")
                    st.write("2. After authorization, copy the code from the redirect page")
                    st.write("3. Paste the authorization code below:")
                    
                    # Ask user to paste the code
                    auth_code = st.text_input("Authorization Code:", key="auth_code")
                    
                    if auth_code and len(auth_code) > 10:
                        try:
                            flow.fetch_token(code=auth_code.strip())
                            creds = flow.credentials
                            
                            # Save the credentials for the next run
                            with open('token.pickle', 'wb') as token:
                                pickle.dump(creds, token)
                            
                            # Set up the service immediately
                            self.credentials = creds
                            self.service = build('gmail', 'v1', credentials=creds)
                            
                            st.success("✅ Authentication successful!")
                            # Clear the auth code and auth state
                            st.session_state.auth_in_progress = False
                            if 'auth_code' in st.session_state:
                                del st.session_state['auth_code']
                            return True
                        except Exception as e:
                            st.error(f"Invalid authorization code: {str(e)}")
                            return False
                    elif auth_code:
                        st.warning("Please enter a valid authorization code")
                        return False
                    else:
                        return False
            
            self.credentials = creds
            self.service = build('gmail', 'v1', credentials=creds)
            return True
            
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            return False
    
    def get_emails(self, start_date: datetime, end_date: datetime, max_results: int = 200) -> List[Dict]:
        """Fetch emails from Gmail within the specified date range"""
        if not self.service:
            raise Exception("Gmail service not authenticated")
        
        try:
            # Start with a very broad search to ensure we can access emails
            start_date_str = start_date.strftime('%Y/%m/%d')
            end_date_str = end_date.strftime('%Y/%m/%d')
            
            # Try a simple date-based query first to test Gmail access
            simple_query = f"after:{start_date_str} before:{end_date_str}"
            st.info(f"🔍 Testing Gmail access with simple query: {simple_query}")
            
            # Search for messages with simple query first
            try:
                result = self.service.users().messages().list(
                    userId='me',
                    q=simple_query,
                    maxResults=50  # Start with a smaller number
                ).execute()
                
                all_messages = result.get('messages', [])
                st.info(f"📧 Found {len(all_messages)} total emails in date range")
                
                if len(all_messages) == 0:
                    st.warning("No emails found in the specified date range. Try increasing the days back.")
                    return []
                
            except Exception as e:
                st.error(f"❌ Failed to access Gmail: {str(e)}")
                return []
            
            # Search specifically for order confirmations, not promotions
            order_terms = [
                "order confirmation", 
                "purchase confirmation",
                "your order",
                "order number",
                "tracking number", 
                "shipment confirmation",
                "delivery confirmation",
                "order receipt",
                "thank you for your order"
            ]
            
            # Exclude promotional terms
            exclude_terms = [
                "-unsubscribe",
                "-promotional", 
                "-sale",
                "-deal",
                "-offer",
                "-discount",
                "-newsletter"
            ]
            
            # Build the query with proper string formatting
            quoted_terms = [f'"{term}"' for term in order_terms]
            terms_part = ' OR '.join(quoted_terms)
            exclude_part = ' '.join(exclude_terms)
            order_query = f"after:{start_date_str} before:{end_date_str} ({terms_part}) {exclude_part}"
            st.info(f"🔍 Searching for order confirmations: {order_query}")
            
            try:
                result = self.service.users().messages().list(
                    userId='me',
                    q=order_query,
                    maxResults=max_results
                ).execute()
                
                messages = result.get('messages', [])
                st.success(f"📧 Found {len(messages)} potential order emails")
                
                # If no order emails found, use broader search
                if len(messages) == 0:
                    st.info("No order-specific emails found, using broader search...")
                    messages = all_messages[:max_results]  # Take from all emails
                    
            except Exception as e:
                st.warning(f"Order search failed: {str(e)}, using broader search")
                messages = all_messages[:max_results]
            
            # Fetch full message details
            emails = []
            st.info(f"📥 Fetching details for {len(messages)} emails...")
            
            for i, message in enumerate(messages):
                try:
                    if i % 10 == 0:  # Show progress every 10 emails
                        st.info(f"Processing email {i+1}/{len(messages)}")
                    
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()
                    
                    email_data = self._parse_message(msg)
                    if email_data:
                        emails.append(email_data)
                        
                except Exception as e:
                    st.warning(f"Error fetching message {i+1}: {str(e)}")
                    continue
            
            st.success(f"✅ Successfully fetched {len(emails)} emails")
            return emails
            
        except HttpError as error:
            st.error(f"An error occurred: {error}")
            return []
    
    def _parse_message(self, message: Dict) -> Optional[Dict]:
        """Parse Gmail message into structured data"""
        try:
            headers = message['payload'].get('headers', [])
            
            # Extract headers
            subject = ''
            sender = ''
            date = ''
            
            for header in headers:
                name = header.get('name', '').lower()
                value = header.get('value', '')
                
                if name == 'subject':
                    subject = value
                elif name == 'from':
                    sender = value
                elif name == 'date':
                    date = value
            
            # Extract body
            body = self._extract_body(message['payload'])
            
            # Parse date
            try:
                parsed_date = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %z')
            except:
                try:
                    # Alternative date format
                    parsed_date = datetime.strptime(date.split(' (')[0], '%a, %d %b %Y %H:%M:%S %z')
                except:
                    parsed_date = datetime.now(timezone.utc)
            
            return {
                'id': message['id'],
                'subject': subject,
                'sender': sender,
                'date': parsed_date,
                'body': body
            }
            
        except Exception as e:
            st.warning(f"Error parsing message: {str(e)}")
            return None
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from message payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'parts' in part:
                    body += self._extract_body(part)
        else:
            if payload['mimeType'] == 'text/plain' or payload['mimeType'] == 'text/html':
                if 'data' in payload['body']:
                    body += base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        return body
