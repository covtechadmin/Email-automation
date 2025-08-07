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

try:
    from streamlit_quill import st_quill
    RICH_TEXT_AVAILABLE = True
except ImportError:
    RICH_TEXT_AVAILABLE = False

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re

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

def replace_template_variables(template: str, replacements: Dict[str, str], is_html: bool = False) -> str:
    """Replace template variables with actual values"""
    result = template
    
    if is_html:
        # For HTML content, we need to be more careful about replacements
        # Handle HTML-encoded placeholders and preserve HTML structure
        import html
        
        for key, value in replacements.items():
            placeholder = f"<{key}>"
            safe_value = str(value) if value else ""
            
            # Try multiple replacement patterns for HTML content
            # 1. Direct replacement
            result = result.replace(placeholder, safe_value)
            
            # 2. HTML-encoded replacement (&lt; and &gt;)
            encoded_placeholder = html.escape(placeholder)
            result = result.replace(encoded_placeholder, safe_value)
            
            # 3. Handle placeholders that might be split across tags
            # Look for patterns like <span><{key}></span> or similar
            pattern = rf'(<[^>]*>)*\s*<\s*{re.escape(key)}\s*>\s*(<[^>]*>)*'
            result = re.sub(pattern, safe_value, result, flags=re.IGNORECASE)
            
            # 4. Handle placeholders with extra whitespace
            spaced_placeholder = f"< {key} >"
            result = result.replace(spaced_placeholder, safe_value)
            
    else:
        # Plain text replacement (original logic)
        for key, value in replacements.items():
            placeholder = f"<{key}>"
            result = result.replace(placeholder, str(value) if value else "")
    
    return result

def convert_to_html(text: str, is_html: bool = False) -> str:
    """Convert plain text or HTML to formatted HTML email"""
    if not text:
        return ""
    
    import re
    
    if is_html:
        # Text is already HTML (from rich text editor or EML)
        html_text = text
        
        # Clean up any existing body/html tags to avoid nesting
        html_text = re.sub(r'</?html[^>]*>', '', html_text, flags=re.IGNORECASE)
        html_text = re.sub(r'</?body[^>]*>', '', html_text, flags=re.IGNORECASE)
        html_text = re.sub(r'</?head[^>]*>', '', html_text, flags=re.IGNORECASE)
        html_text = re.sub(r'<meta[^>]*>', '', html_text, flags=re.IGNORECASE)
        
        # Remove any extra whitespace but preserve intentional formatting
        html_text = html_text.strip()
        
        # Wrap in minimal email structure without overriding styles
        html_text = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0;">
    <div>
        {html_text}
    </div>
</body>
</html>"""
        return html_text
    
    # Handle plain text with markdown formatting while preserving structure
    html_text = text
    
    # Convert markdown-style formatting to HTML
    # Bold text: **text** or __text__ -> <strong>text</strong>
    html_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html_text)
    html_text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', html_text)
    
    # Italic text: *text* or _text_ -> <em>text</em>
    html_text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', html_text)
    html_text = re.sub(r'(?<!_)_([^_]+?)_(?!_)', r'<em>\1</em>', html_text)
    
    # Convert hyperlink syntax [text](url) to HTML links
    hyperlink_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    html_text = re.sub(hyperlink_pattern, r'<a href="\2" style="color: #0066cc; text-decoration: underline;">\1</a>', html_text)
    
    # Convert simple URLs to clickable links
    url_pattern = r'(?<!href=")(?<!href=\')(?<!<a href=")(?<!<a href=\')(?<!>)https?://[^\s<>"\']+(?!["\']>)(?!</a>)'
    html_text = re.sub(url_pattern, r'<a href="\g<0>" style="color: #0066cc; text-decoration: underline;">\g<0></a>', html_text)
    
    # Preserve exact line breaks and spacing
    # Replace newlines with <br> tags but handle multiple consecutive newlines properly
    html_text = re.sub(r'\n{3,}', '\n\n', html_text)  # Limit excessive line breaks
    html_text = html_text.replace('\n', '<br>\n')
    
    # Wrap in minimal HTML structure without imposed styling
    html_text = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 10px; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.4;">
    <div>
        {html_text}
    </div>
</body>
</html>"""
    
    return html_text

def parse_eml_file(eml_content: bytes) -> Dict[str, str]:
    """Parse EML file and extract subject, HTML body, and plain text body"""
    try:
        # Parse the email message
        msg = email.message_from_bytes(eml_content)
        
        # Extract subject
        subject = msg.get('Subject', '')
        if subject:
            # Decode subject if it's encoded
            from email.header import decode_header
            decoded_subject = decode_header(subject)
            subject = ''.join([
                text.decode(encoding or 'utf-8') if isinstance(text, bytes) else text
                for text, encoding in decoded_subject
            ])
        
        # Extract body content
        html_body = ""
        plain_body = ""
        
        if msg.is_multipart():
            # Handle multipart messages
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                    
                if content_type == "text/plain":
                    plain_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html":
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            # Handle simple messages
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                plain_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == "text/html":
                html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # Clean up HTML body if present
        if html_body:
            # Keep only the main content between <body> tags if present
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_body, re.DOTALL | re.IGNORECASE)
            if body_match:
                html_body = body_match.group(1)
            
            # Remove only problematic style attributes, keep formatting ones
            # Remove only width/height constraints that might break in different clients
            html_body = re.sub(r'width\s*:\s*[^;}"\'\s]*[;"\']', '', html_body, flags=re.IGNORECASE)
            html_body = re.sub(r'max-width\s*:\s*[^;}"\'\s]*[;"\']', '', html_body, flags=re.IGNORECASE)
            
            # Preserve all other formatting and spacing
            html_body = html_body.strip()
        
        return {
            'subject': subject,
            'html_body': html_body,
            'plain_body': plain_body
        }
        
    except Exception as e:
        st.error(f"Error parsing EML file: {str(e)}")
        return {'subject': '', 'html_body': '', 'plain_body': ''}

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
    
    st.title("📧 Covvalent Email Automation Tool")
    st.markdown("Automate email sending to multiple contacts (up to 200) using templated emails. Have Fun: from Nikhil :)")

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
    
    # Template input method selection
    template_method = st.radio(
        "Choose how to create your email template:",
        ["Type/Paste Template", "Upload EML File"],
        help="Upload EML to preserve exact formatting from saved emails"
    )
    
    # Initialize template variables
    email_template = ""
    subject_template = ""
    is_rich_text = False
    
    if template_method == "Upload EML File":
        st.info("""
        **EML File Upload:**
        - Save an email as .eml file from your email client (Outlook: File → Save As → Outlook Message Format)
        - Upload it here to preserve all formatting, styles, and layout
        - Add `<Column Name>` placeholders where you want dynamic content
        - Subject and body will be automatically extracted
        """)
        
        uploaded_eml = st.file_uploader(
            "Upload EML email file",
            type=['eml'],
            help="Upload a saved email file (.eml format)"
        )
        
        if uploaded_eml:
            eml_data = parse_eml_file(uploaded_eml.read())
            
            if eml_data['subject'] or eml_data['html_body'] or eml_data['plain_body']:
                st.success("✅ EML file loaded successfully!")
                
                # Show extracted content
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Extracted Subject:")
                    subject_template = st.text_input(
                        "Edit subject template:",
                        value=eml_data['subject'],
                        help="Add <Column Name> placeholders for dynamic content"
                    )
                
                with col2:
                    st.subheader("Content Preview:")
                    if eml_data['html_body']:
                        st.write("✅ Rich HTML formatting detected")
                        email_template = eml_data['html_body']
                        is_rich_text = True
                    else:
                        st.write("📝 Plain text content detected")
                        email_template = eml_data['plain_body']
                        is_rich_text = False
                
                # Allow editing the template with placeholders
                st.subheader("Edit Template (Add placeholders like <Customer Name>):")
                if is_rich_text and RICH_TEXT_AVAILABLE:
                    email_template = st_quill(
                        value=email_template,
                        html=True,
                        toolbar=[
                            ['bold', 'italic', 'underline'],
                            ['link'],
                            [{'list': 'ordered'}, {'list': 'bullet'}],
                            ['clean']
                        ],
                        key="eml_template_editor"
                    )
                else:
                    email_template = st.text_area(
                        "Email body template:",
                        value=email_template,
                        height=400,
                        help="Add <Column Name> placeholders for dynamic content"
                    )
                    if is_rich_text:
                        st.info("💡 Install `streamlit-quill` to edit with rich text formatting")
            else:
                st.error("Could not extract content from EML file. Please check the file format.")
    
    else:
        # Original template creation method
        # Editor type selection
        if RICH_TEXT_AVAILABLE:
            editor_type = st.radio(
                "Choose editor type:",
                ["Simple Text Editor", "Rich Text Editor (with formatting)"],
                help="Rich text editor allows pasting formatted text from email clients"
            )
        else:
            editor_type = "Simple Text Editor"
            st.info("💡 **Tip:** Install `streamlit-quill` to enable rich text editor with copy-paste formatting support")
        
        if editor_type == "Rich Text Editor (with formatting)" and RICH_TEXT_AVAILABLE:
            st.info("""
            **Rich Text Editor Tips:**
            - Paste formatted text directly from your email client
            - Use the toolbar for formatting (Bold, Italic, etc.)
            - Use `<Column Name>` for dynamic content from your Excel file
            - Insert links using the link button in toolbar
            """)
            
            email_template = st_quill(
                placeholder="Dear <Customer Name>, \n\nI hope this email finds you well...",
                html=True,
                toolbar=[
                    ['bold', 'italic', 'underline'],
                    ['link'],
                    [{'list': 'ordered'}, {'list': 'bullet'}],
                    ['clean']
                ],
                key="email_template"
            )
            is_rich_text = True
        else:
            # Add help text for simple editor
            st.info("""
            **Formatting Tips:**
            - Use `<Column Name>` for dynamic content from your Excel file
            - **Bold text**: Use `**bold text**` or `__bold text__`
            - *Italic text*: Use `*italic text*` or `_italic text_`
            - Create hyperlinks with `[Link Text](https://example.com)`
            - Plain URLs like `https://example.com` will automatically become clickable
            - Use double line breaks for new paragraphs
            """)
            
            email_template = st.text_area(
                "Email Body Template",
                placeholder="""Dear <Customer Name>,

I hope this email finds you well. I am reaching out from our team regarding **<Company Name>**.

We would like to discuss *potential collaboration opportunities* with <Company Name>.

**Key Benefits:**
- Professional service
- Competitive pricing
- 24/7 support

Please visit our website at [Company Website](https://www.example.com) to learn more about us.

You can also schedule a meeting with us: https://calendly.com/yourname

Best regards,
**Your Name**
*Your Title*""",
                height=300,
                help="Use markdown-style formatting, links [text](url) and template variables <column_name>"
            )
            is_rich_text = False
    
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
            
            preview_subject = replace_template_variables(subject_template, preview_data, is_html=False)
            preview_body = replace_template_variables(email_template, preview_data, is_html=is_rich_text)
            preview_body_html = convert_to_html(preview_body, is_html=is_rich_text)
            
            st.subheader("Subject:")
            st.code(preview_subject)
            
            if is_rich_text:
                st.subheader("Email Preview (What recipients will see):")
                st.components.v1.html(preview_body_html, height=400, scrolling=True)
            else:
                st.subheader("Body (Preview):")
                st.markdown(preview_body)
                
                st.subheader("HTML Email Body (What recipients will see):")
                st.components.v1.html(preview_body_html, height=300, scrolling=True)
    
    # Send emails section
    st.header("🚀 Send Emails")
    
    # Show batch size information
    if df is not None:
        batch_size = len(df)
        estimated_time = batch_size * (0.5 if batch_size > 100 else 1) / 60  # minutes
        st.info(f"**Batch Info:** {batch_size} recipients | Estimated time: {estimated_time:.1f} minutes")
        
        if batch_size > 500:
            st.warning("⚠️ Large batch detected. Consider splitting into smaller batches for better reliability.")
    
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
                final_subject = replace_template_variables(subject_template, contact_data, is_html=False)
                final_body = replace_template_variables(email_template, contact_data, is_html=is_rich_text)
                final_body_html = convert_to_html(final_body, is_html=is_rich_text)
                
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
                
                # Dynamic delay based on batch size to avoid rate limiting
                if len(df) > 100:
                    time.sleep(0.5)  # Faster for large batches
                else:
                    time.sleep(1)    # Conservative for small batches
                
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
