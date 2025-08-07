import streamlit as st
import pandas as pd
import requests
import json
import base64
from msal import ConfidentialClientApplication
from dotenv import load_dotenv
import os
from typing import List, Dict, Optional
import time

# Load environment variables
load_dotenv()

class AzureGraphClient:
    def __init__(self):
        self.client_id = os.getenv('AZURE_CLIENT_ID')
        self.client_secret = os.getenv('AZURE_CLIENT_SECRET')
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.access_token = None
        
        # Initialize MSAL app
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )
    
    def get_access_token(self):
        """Get access token for Microsoft Graph API"""
        try:
            result = self.app.acquire_token_silent(self.scope, account=None)
            
            if not result:
                result = self.app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                return True
            else:
                st.error(f"Failed to get access token: {result.get('error_description', 'Unknown error')}")
                return False
        except Exception as e:
            st.error(f"Error getting access token: {str(e)}")
            return False
    
    def send_email(self, from_email: str, to_email: str, cc_emails: List[str], 
                   subject: str, body: str, attachment_data: Optional[bytes] = None, 
                   attachment_name: Optional[str] = None) -> bool:
        """Send email using Microsoft Graph API"""
        if not self.access_token:
            if not self.get_access_token():
                return False
        
        # Prepare email message
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": to_email
                    }
                }
            ]
        }
        
        # Add CC recipients if provided
        if cc_emails:
            message["ccRecipients"] = [
                {"emailAddress": {"address": email}} for email in cc_emails if email.strip()
            ]
        
        # Add attachment if provided
        if attachment_data and attachment_name:
            attachment_base64 = base64.b64encode(attachment_data).decode('utf-8')
            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment_name,
                    "contentType": "application/octet-stream",
                    "contentBytes": attachment_base64
                }
            ]
        
        # API endpoint
        url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "message": message,
            "saveToSentItems": "true"
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            if response.status_code == 202:
                return True
            else:
                st.error(f"Failed to send email to {to_email}. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            st.error(f"Error sending email to {to_email}: {str(e)}")
            return False

def replace_template_variables(template: str, replacements: Dict[str, str]) -> str:
    """Replace template variables with actual values"""
    result = template
    for key, value in replacements.items():
        placeholder = f"<{key}>"
        result = result.replace(placeholder, str(value) if value else "")
    return result

def convert_to_html(text: str) -> str:
    """Convert plain text to HTML, preserving formatting and converting hyperlinks"""
    if not text:
        return ""
    
    # Replace newlines with <br> tags
    html_text = text.replace('\n', '<br>')
    
    # Convert hyperlink syntax [text](url) to HTML links
    import re
    hyperlink_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    html_text = re.sub(hyperlink_pattern, r'<a href="\2" style="color: #0066cc; text-decoration: none;">\1</a>', html_text)
    
    # Convert simple URLs to clickable links
    url_pattern = r'(?<!href=")(?<!href=\')(?<!<a href=")(?<!<a href=\')https?://[^\s<>"\']+(?!["\']>)'
    html_text = re.sub(url_pattern, r'<a href="\g<0>" style="color: #0066cc; text-decoration: none;">\g<0></a>', html_text)
    
    # Wrap in basic HTML structure
    html_text = f"""
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    {html_text}
    </div>
    </body>
    </html>
    """
    
    return html_text

def validate_excel_columns(df: pd.DataFrame) -> bool:
    """Validate that the Excel file has required columns"""
    required_columns = ['Company Name', 'Company Email', 'Customer Name']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {', '.join(missing_columns)}")
        st.info("Required columns: Company Name, Company Email, Customer Name")
        return False
    return True

def main():
    st.set_page_config(page_title="Email Automation App", page_icon="📧", layout="wide")
    
    st.title("📧 Email Automation with Azure Graph")
    st.markdown("Automate email sending to multiple contacts using templated emails and Azure Graph API")
    
    # Sidebar for configuration
    st.sidebar.header("Configuration")
    
    # Check if environment variables are set
    if not all([os.getenv('AZURE_CLIENT_ID'), os.getenv('AZURE_CLIENT_SECRET'), os.getenv('AZURE_TENANT_ID')]):
        st.error("Please configure your Azure credentials in the .env file")
        st.info("Copy .env.example to .env and fill in your Azure app registration details")
        return
    
    # Initialize Azure Graph client
    graph_client = AzureGraphClient()
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📊 Excel File Upload")
        uploaded_excel = st.file_uploader(
            "Upload Excel file with contacts",
            type=['xlsx', 'xls'],
            help="Excel file should contain: Company Name, Company Email, Customer Name"
        )
        
        if uploaded_excel:
            try:
                df = pd.read_excel(uploaded_excel)
                st.success(f"Excel file loaded successfully! Found {len(df)} contacts.")
                
                if validate_excel_columns(df):
                    st.dataframe(df.head(), use_container_width=True)
                    
                    # Show available columns for template variables
                    st.subheader("Available Template Variables")
                    st.info("You can use these in your email template: " + 
                           ", ".join([f"<{col}>" for col in df.columns]))
                else:
                    df = None
            except Exception as e:
                st.error(f"Error reading Excel file: {str(e)}")
                df = None
        else:
            df = None
    
    with col2:
        st.header("📎 Attachment File")
        uploaded_attachment = st.file_uploader(
            "Upload attachment file (optional)",
            type=None,
            help="This file will be attached to all emails"
        )
        
        if uploaded_attachment:
            st.success(f"Attachment uploaded: {uploaded_attachment.name}")
            st.info(f"File size: {len(uploaded_attachment.getvalue())} bytes")
    
    # Email configuration
    st.header("✉️ Email Configuration")
    
    col3, col4 = st.columns([1, 1])
    
    with col3:
        from_email = st.text_input(
            "From Email Address",
            placeholder="sender@company.com",
            help="The email address that will send the emails"
        )
        
        subject_template = st.text_input(
            "Email Subject Template",
            placeholder="Hello <Customer Name> from <Company Name>",
            help="Use <column_name> for dynamic content"
        )
    
    with col4:
        cc_emails_input = st.text_area(
            "CC Email Addresses (optional)",
            placeholder="email1@company.com\nemail2@company.com",
            help="One email per line"
        )
        
        cc_emails = [email.strip() for email in cc_emails_input.split('\n') if email.strip()]
    
    # Email template
    st.header("📝 Email Template")
    
    # Add help text for hyperlinks
    st.info("""
    **Formatting Tips:**
    - Use `<Column Name>` for dynamic content from your Excel file
    - Create hyperlinks with `[Link Text](https://example.com)`
    - Plain URLs like `https://example.com` will automatically become clickable
    - Line breaks will be preserved in the email
    """)
    
    email_template = st.text_area(
        "Email Body Template",
        placeholder="""Dear <Customer Name>,

I hope this email finds you well. I am reaching out from our team regarding <Company Name>.

We would like to discuss potential collaboration opportunities with <Company Name>.

Please visit our website at [Company Website](https://www.example.com) to learn more about us.

You can also schedule a meeting with us: https://calendly.com/yourname

Best regards,
Your Name""",
        height=250,
        help="Use markdown-style links [text](url) and template variables <column_name>"
    )
    
    # Preview section
    if df is not None and email_template and subject_template:
        st.header("👀 Email Preview")
        
        preview_index = st.selectbox(
            "Select contact for preview:",
            range(len(df)),
            format_func=lambda x: f"{df.iloc[x]['Customer Name']} - {df.iloc[x]['Company Name']}"
        )
        
        if preview_index is not None:
            preview_data = df.iloc[preview_index].to_dict()
            
            preview_subject = replace_template_variables(subject_template, preview_data)
            preview_body = replace_template_variables(email_template, preview_data)
            preview_body_html = convert_to_html(preview_body)
            
            st.subheader("Subject:")
            st.code(preview_subject)
            
            st.subheader("Body (Preview):")
            st.markdown(preview_body)
            
            st.subheader("HTML Email Body (What recipients will see):")
            st.components.v1.html(preview_body_html, height=300, scrolling=True)
    
    # Send emails section
    st.header("🚀 Send Emails")
    
    if st.button("Send Emails to All Contacts", type="primary", disabled=(df is None or not email_template or not from_email)):
        if df is None:
            st.error("Please upload an Excel file first")
            return
        
        if not email_template or not from_email:
            st.error("Please fill in all required fields")
            return
        
        # Test authentication first
        with st.spinner("Testing Azure Graph connection..."):
            if not graph_client.get_access_token():
                st.error("Failed to authenticate with Azure Graph API")
                return
        
        st.success("Successfully authenticated with Azure Graph API")
        
        # Send emails
        progress_bar = st.progress(0)
        status_container = st.container()
        
        successful_sends = 0
        failed_sends = 0
        
        for index, row in df.iterrows():
            try:
                # Prepare email data
                contact_data = row.to_dict()
                final_subject = replace_template_variables(subject_template, contact_data)
                final_body = replace_template_variables(email_template, contact_data)
                final_body_html = convert_to_html(final_body)
                
                # Get attachment data if available
                attachment_data = None
                attachment_name = None
                if uploaded_attachment:
                    attachment_data = uploaded_attachment.getvalue()
                    attachment_name = uploaded_attachment.name
                
                # Send email
                with status_container:
                    st.write(f"Sending email to {row['Customer Name']} at {row['Company Email']}...")
                
                success = graph_client.send_email(
                    from_email=from_email,
                    to_email=row['Company Email'],
                    cc_emails=cc_emails,
                    subject=final_subject,
                    body=final_body_html,
                    attachment_data=attachment_data,
                    attachment_name=attachment_name
                )
                
                if success:
                    successful_sends += 1
                    with status_container:
                        st.success(f"✅ Email sent to {row['Customer Name']}")
                else:
                    failed_sends += 1
                    with status_container:
                        st.error(f"❌ Failed to send email to {row['Customer Name']}")
                
                # Update progress
                progress = (index + 1) / len(df)
                progress_bar.progress(progress)
                
                # Small delay to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                failed_sends += 1
                with status_container:
                    st.error(f"❌ Error sending to {row['Customer Name']}: {str(e)}")
        
        # Final summary
        st.header("📊 Email Sending Summary")
        col5, col6 = st.columns(2)
        
        with col5:
            st.metric("Successful Emails", successful_sends)
        
        with col6:
            st.metric("Failed Emails", failed_sends)
        
        if successful_sends > 0:
            st.success(f"Email campaign completed! {successful_sends} emails sent successfully.")
        
        if failed_sends > 0:
            st.warning(f"{failed_sends} emails failed to send. Check the error messages above.")

if __name__ == "__main__":
    main()
