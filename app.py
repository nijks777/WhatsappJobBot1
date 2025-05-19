from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pyodbc
import requests
from datetime import datetime
import io
import os
import base64
from flask import make_response
app = Flask(__name__)
CORS(app)  # Enable CORS

# Database connection setup

# Database connection setup
db_config = {
    'server': os.getenv('DB_SERVER', 'jobbot.database.windows.net'),
    'database': os.getenv('DB_NAME', 'JobBot1'),
    'username': os.getenv('DB_USERNAME', 'WHATSAPPJOBBOT'),
    'password': os.getenv('DB_PASSWORD', 'Conor2260$'),
    'driver': '{ODBC Driver 17 for SQL Server}'
}

# Build connection string for Azure SQL
connection_string = f"DRIVER={db_config['driver']};SERVER={db_config['server']};DATABASE={db_config['database']};UID={db_config['username']};PWD={db_config['password']};"

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get WhatsApp access token from environment variables
access_token = os.getenv('WHATSAPP_ACCESS_TOKEN')

# Add this check to ensure the token was loaded correctly
if not access_token:
    print("WARNING: WhatsApp access token not found in environment variables!")
else:
    print(f"WhatsApp token loaded successfully (length: {len(access_token)})")

# WhatsApp API configuration
whatsapp_api_url = "https://graph.facebook.com/v22.0/442282912309247/messages"
def send_thank_you_message(candidate_id, name, mobile):
    """
    Send a thank you message after resume upload with edit options
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": f"Dear {name},\n\nThank you for completing your application! We have received all your responses and your resume.\n\nWould you like to review or edit any of your previous responses?"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"edit_{candidate_id}_all", "title": "Review/Edit"}},
                    {"type": "reply", "reply": {"id": f"edit_{candidate_id}_none", "title": "No, Thanks"}}
                ]
            }
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200
@app.route('/add-candidate', methods=['POST'])
def add_candidate():
    try:
        data = request.json
        name = data.get('name')
        mobile = data.get('mobile')
        job_description = data.get('jobDescription')
        shortlistId = data.get('shortlistId')
        userId = data.get('userId')
        
        if not name or not mobile:
            return jsonify({"error": "Name and mobile are required"}), 400
            
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # Check if a candidate with this mobile number already exists
        cursor.execute(
            "SELECT CandidateID FROM Candidates WHERE Mobile = ? AND ShortlistID = ? AND UserID = ?",
            (mobile, shortlistId, userId)
        )
        existing_candidate = cursor.fetchone()
        
        if existing_candidate:
            # Update the existing candidate
            cursor.execute("""
                UPDATE Candidates 
                SET Name = ?, JobDescription = ?
                WHERE Mobile = ?
            """, (name, job_description, mobile))
            candidate_id = existing_candidate.CandidateID
            status_message = "Candidate updated successfully"
        else:
            # Insert a new candidate
            cursor.execute("""
                INSERT INTO Candidates (Name, Mobile, JobDescription, ShortlistId, UserId)
                VALUES (?, ?, ?, ?, ?)
            """, (name, mobile, job_description, shortlistId, userId))
            # Get the newly inserted candidate ID
            cursor.execute("SELECT @@IDENTITY")
            candidate_id = cursor.fetchone()[0]
            status_message = "Candidate added successfully"
            
        conn.commit()
        
        return jsonify({
            "status": status_message,
            "candidateId": candidate_id
        }), 200
        
    except Exception as e:
        print(f"Error adding candidate: {str(e)}")
        return jsonify({"error": str(e)}), 500
def send_comprehensive_edit_options(candidate_id, name, mobile):
    """
    Send a simplified edit options message via WhatsApp
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "text",
        "text": {
            "body": f"Hi {name}, if you want to edit any of your previous responses, you can select the corresponding option from the previous questions. Simply choose the New option."
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200
def send_resume_request(candidate_id, name, mobile):
    """
    Send resume upload request via WhatsApp
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "text",
        "text": {
            "body": f"Hi {name}, We need one last thing from you. Please share your Updated resume.If already done You can leave it."
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

@app.route('/upload-resume', methods=['POST'])
def upload_resume():
    """
    API endpoint to upload resume manually (optional, for testing)
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        candidate_id = request.form.get('candidate_id')
        
        if not candidate_id:
            return jsonify({"error": "Candidate ID is required"}), 400
        
        # Check file extension
        allowed_extensions = ['.pdf', '.doc', '.docx']
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({"error": "Only PDF, DOC, and DOCX files are allowed"}), 400
        
        # Read file content
        file_content = file.read()
        
        # Connect to database
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        try:
            # Update responses table with resume
            cursor.execute("""
                UPDATE Responses 
                SET ResumeFileName = ?, 
                    ResumeFileData = ?, 
                    ResumeFileType = ?,
                    ResumeUploadDate = ? 
                WHERE CandidateID = ?
            """, (
                file.filename, 
                file_content, 
                file_ext,  # Store file type
                datetime.now(), 
                candidate_id
            ))
            conn.commit()
            
            return jsonify({"message": "Resume uploaded successfully"}), 200
        
        except Exception as db_error:
            conn.rollback()
            return jsonify({"error": str(db_error)}), 500
        finally:
            cursor.close()
            conn.close()
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-resume/<int:candidate_id>', methods=['GET'])
def get_resume(candidate_id):
    """
    API endpoint to retrieve resume
    """
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ResumeFileName, ResumeFileData, ResumeFileType 
            FROM Responses 
            WHERE CandidateID = ?
        """, (candidate_id,))
        
        result = cursor.fetchone()
        
        if result and result.ResumeFileData:
            # Determine mime type based on file extension
            file_ext = os.path.splitext(result.ResumeFileName)[1].lower()
            mime_types = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            
            # Fallback to stored ResumeFileType if available
            if result.ResumeFileType:
                file_ext = result.ResumeFileType.lower()
            
            mime_type = mime_types.get(file_ext, 'application/octet-stream')
            
            # Create a response with the file content
            response = make_response(result.ResumeFileData)
            response.headers['Content-Disposition'] = f'attachment; filename={result.ResumeFileName}'
            response.headers['Content-Type'] = mime_type
            
            return response
        else:
            return jsonify({"error": "Resume not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def send_notice_period_question(candidate_id, name, mobile):
    """
    Send notice period question as an interactive message
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Almost done!\n\nWhat is your Notice Period?"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"noticeperiod_{candidate_id}_immediate", "title": "Immediate"}},
                    {"type": "reply", "reply": {"id": f"noticeperiod_{candidate_id}_15days", "title": "15 Days"}},
                    {"type": "reply", "reply": {"id": f"noticeperiod_{candidate_id}_30days", "title": "30 Days"}}
                ]
            }
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

def send_expected_ctc_question(candidate_id, name, mobile):
    """
    Send expected CTC question as an interactive message
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Thanks For Your Previous Response:\n\nWhat is your Expected CTC?"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"expectedctc_{candidate_id}_4-6", "title": "4-6 LPA"}},
                    {"type": "reply", "reply": {"id": f"expectedctc_{candidate_id}_6-8", "title": "6-8 LPA"}},
                    {"type": "reply", "reply": {"id": f"expectedctc_{candidate_id}_8-10", "title": "8-10 LPA"}}
                ]
            }
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

def send_salary_question(candidate_id, name, mobile):
    """
    Send salary question as an interactive message
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Thank you for sharing your location. Please answer the following question:\n\nCurrent Salary/CTC?"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"salary_{candidate_id}_0-3", "title": "0-3 LPA"}},
                    {"type": "reply", "reply": {"id": f"salary_{candidate_id}_3-6", "title": "3-6 LPA"}},
                    {"type": "reply", "reply": {"id": f"salary_{candidate_id}_6-10", "title": "6-10 LPA"}}
                ]
            }
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

# Add this new function to your Flask application (paste.txt)

# Updated function to send message based on mobile number

@app.route('/send-individual-message', methods=['POST'])
def send_individual_message():
    try:
        data = request.json
        mobile = data.get('mobile')
        userId = data.get('userId')
        shortlistId = data.get('shortlistId')
        
        if not mobile:
            return jsonify({"error": "Mobile number is required"}), 400
            
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch the specific candidate from the database based on mobile number
        cursor.execute("SELECT CandidateID, Name, Mobile, JobDescription FROM Candidates WHERE Mobile = ? AND ShortlistID = ? AND UserID = ?",
            (mobile, shortlistId, userId)
        )
        candidate = cursor.fetchone()

        # If candidate exists, use their info
        if candidate:
            candidate_id, name, mobile, job_desc = candidate
        else:
            return jsonify({"error": "Error: No candidate exist."}), 400
        
        # Prepare the WhatsApp API request with job opportunity message
        message = {
            "messaging_product": "whatsapp",
            "to": f"{mobile}",
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "text",
                    "text": "Company Ltd. - Job Opportunity"
                },
                "body": {
                    "text": f"Dear {name},\n\n" + 
                    "Greetings from Tech Mahindra Ltd.!\n\n" +
                    f"I am from the RMG Group at Tech Mahindra. We have reviewed your profile and are excited to share that your qualifications align with our {job_desc} job opening.\n\n" +
                    f"Job Description – {job_desc}\n" +
                    ". Collect, clean, and organize large datasets to ensure accuracy and consistency.\n" +
                    ". Analyze data to identify trends, patterns, and actionable insights to support decision-making.\n" +
                    ". Create interactive dashboards and reports using tools such as Power BI, Tableau, or Excel.\n" +
                    ". Write and optimize SQL queries for data extraction and manipulation.\n" +
                    ". Collaborate with cross-functional teams to understand business needs and deliver solutions.\n" +
                    ". Present findings through clear visualizations and presentations tailored for stakeholders.\n" +
                    ". Stay updated on industry trends, data analysis tools, and techniques to drive performance improvements.\n\n" +
                    "If you are interested in this opportunity, please press \"Yes\" to proceed further."
                },
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": f"yes_{candidate_id}", "title": "Yes"}},
                        {"type": "reply", "reply": {"id": f"no_{candidate_id}", "title": "No"}}
                    ]
                }
            }
        }

        # Send message via WhatsApp API
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(whatsapp_api_url, json=message, headers=headers)

        if response.status_code != 200:
            print(f"Failed to send message to {mobile}: {response.json()}")
            return jsonify({"error": f"Failed to send message to {mobile}"}), 500

        return jsonify({"status": f"Message sent successfully to {mobile}"}), 200

    except Exception as e:
        print(f"Error sending individual message: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/candidates', methods=['GET'])
def get_candidates():
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch all candidates from the database with message sent status
        cursor.execute("""
            SELECT 
                c.CandidateID, 
                c.Name, 
                c.Mobile,
                c.ShortlistId,
                c.UserId,
                CASE 
                    WHEN r.ResponseDate IS NOT NULL THEN 1 
                    ELSE 0 
                END as MessageSent
            FROM Candidates c
            LEFT JOIN Responses r ON c.CandidateID = r.CandidateID
        """)
        
        candidates = [
            {
                "CandidateID": row.CandidateID, 
                "Name": row.Name, 
                "Mobile": row.Mobile,
                "ShortlistId": row.ShortlistId,
                "UserId": row.UserId,
                "MessageSent": bool(row.MessageSent)
            } 
            for row in cursor.fetchall()
        ]

        return jsonify(candidates), 200
    except Exception as e:
        print("Error fetching candidates:", str(e))
        return jsonify({"error": str(e)}), 500



@app.route('/send-message', methods=['POST'])
def send_message():
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch all candidates from the database
        cursor.execute("SELECT CandidateID, Name, Mobile, JobDescription FROM Candidates")
        candidates = cursor.fetchall()

        if not candidates:
            return jsonify({"error": "No candidates found"}), 400

        # Iterate through candidates and send messages
        for candidate in candidates:
            candidate_id, name, mobile, job_desc = candidate

            # Prepare the WhatsApp API request with new message
            message = {
                "messaging_product": "whatsapp",
                "to": f"{mobile}",
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "header": {
                        "type": "text",
                        "text": "Tech Mahindra Ltd. - Job Opportunity"
                    },
                    "body": {
                        "text": f"Dear {name},\n\n" + 
                        "Greetings from Tech Mahindra Ltd.!\n\n" +
                        "I am Swati from the RMG Group at Tech Mahindra. We have reviewed your profile and are excited to share that your qualifications align with our Data Analyst job opening.\n\n" +
                        "Job Description – Data Analyst\n" +
                        ". Collect, clean, and organize large datasets to ensure accuracy and consistency.\n" +
                        ". Analyze data to identify trends, patterns, and actionable insights to support decision-making.\n" +
                        ". Create interactive dashboards and reports using tools such as Power BI, Tableau, or Excel.\n" +
                        ". Write and optimize SQL queries for data extraction and manipulation.\n" +
                        ". Collaborate with cross-functional teams to understand business needs and deliver solutions.\n" +
                        ". Present findings through clear visualizations and presentations tailored for stakeholders.\n" +
                        ". Stay updated on industry trends, data analysis tools, and techniques to drive performance improvements.\n\n" +
                        "If you are interested in this opportunity, please press \"Yes\" to proceed further."

                    },
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": f"yes_{candidate_id}", "title": "Yes"}},
                            {"type": "reply", "reply": {"id": f"no_{candidate_id}", "title": "No"}}
                        ]
                    }
                }
            }

            # Send message via WhatsApp API
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.post(whatsapp_api_url, json=message, headers=headers)

            if response.status_code != 200:
                print(f"Failed to send message to {mobile}: {response.json()}")

        return jsonify({"status": "Messages sent successfully"}), 200

    except Exception as e:
        print(f"Error sending messages: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        verify_token = "12345"
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            print("Webhook verified successfully.")
            return challenge, 200
        else:
            print("Webhook verification failed.")
            return "Forbidden", 403

    elif request.method == 'POST':
        try:
            data = request.json
            print("Received webhook data:", data)

            # Extract the relevant data from the webhook payload
            if "entry" in data and len(data["entry"]) > 0:
                entry = data["entry"][0]
                if "changes" in entry and len(entry["changes"]) > 0:
                    change = entry["changes"][0]
                    if "value" in change and "messages" in change["value"]:
                        messages = change["value"]["messages"]
                        
                        for message in messages:
                            # Handle document uploads
                            # Handle document uploads
                            if message.get("type") == "document":
                                document = message.get("document", {})
                                mime_type = document.get("mime_type", "")
                                file_name = document.get("filename", "")
                                supported_mime_types = [
                                    "application/pdf",  # PDF
                                    "application/msword",  # DOC
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # DOCX
                                ]
                                # Check if it's a supported document type
                                if mime_type in supported_mime_types:
                                    # Download the document
                                    media_id = message.get("document", {}).get("id")
                                    download_url = f"https://graph.facebook.com/v21.0/{media_id}"
                                    
                                    headers = {
                                        "Authorization": f"Bearer {access_token}"
                                    }
                                    
                                    media_response = requests.get(download_url, headers=headers)
                                    
                                    if media_response.status_code == 200:
                                        media_url = media_response.json().get("url")
                                        
                                        # Download the actual file
                                        file_response = requests.get(media_url, headers=headers)
                                        
                                        if file_response.status_code == 200:
                                            file_content = file_response.content
                                            
                                            # Connect to database to find the candidate
                                            conn = pyodbc.connect(connection_string)
                                            cursor = conn.cursor()
                                            
                                            try:
                                                # Find the most recent candidate who needs a resume upload
                                                cursor.execute("""
                                                    SELECT TOP 1 CandidateID, Name, Mobile 
                                                    FROM Responses 
                                                    WHERE Response = 'Yes'  -- Ensure the candidate has shown interest
                                                    ORDER BY ResponseDate DESC
                                                """)
                                                
                                                candidate = cursor.fetchone()
                                                
                                                if candidate:
                                                    # Update the response with resume
                                                    cursor.execute("""
                                                        UPDATE Responses 
                                                        SET ResumeFileName = ?, 
                                                            ResumeFileData = ?, 
                                                            ResumeUploadDate = ? 
                                                        WHERE CandidateID = ?
                                                    """, (
                                                        file_name, 
                                                        file_content, 
                                                        datetime.now(), 
                                                        candidate.CandidateID
                                                    ))
                                                    conn.commit()
                                                    
                                                    print(f"Resume uploaded for candidate {candidate.CandidateID}")
                                                    # Send thank you message after resume upload
                                                    if send_thank_you_message(candidate.CandidateID, candidate.Name, candidate.Mobile):
                                                        print(f"Sent thank you message to candidate {candidate.CandidateID}")
                                                    else:
                                                        print(f"Failed to send thank you message to candidate {candidate.CandidateID}")
                                            except Exception as db_error:
                                                conn.rollback()
                                                print(f"Database error: {str(db_error)}")
                                                print(f"Detailed error: {str(db_error)}")  # More detailed error logging
                                            finally:
                                                cursor.close()
                                                conn.close()

                        for message in messages:
                            # Handle button reply responses
                            if message.get("type") == "interactive" and "button_reply" in message.get("interactive", {}):
                                button_reply = message["interactive"]["button_reply"]
                                response_id = button_reply["id"]
                                response_text = button_reply["title"]
                                
                                # Get the sender's phone number
                                sender_phone = None
                                if "from" in message:
                                    sender_phone = message["from"]
                                
                                # Initial job interest response (Yes/No)
                                if response_id.startswith("yes_"):
                                    try:
                                        _, candidate_id = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Connect to database
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # First, get candidate details
                                        cursor.execute("""
                                            SELECT Name, Mobile, JobDescription 
                                            FROM Candidates 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Check if response already exists for this candidate
                                            cursor.execute("""
                                                SELECT ResponseID 
                                                FROM Responses 
                                                WHERE CandidateID = ?
                                            """, (candidate_id,))
                                            
                                            existing_response = cursor.fetchone()
                                            
                                            if existing_response:
                                                # Update existing response
                                                cursor.execute("""
                                                    UPDATE Responses 
                                                    SET Response = ?, ResponseDate = ?
                                                    WHERE ResponseID = ?
                                                """, (
                                                    response_text,
                                                    datetime.now(),
                                                    existing_response.ResponseID
                                                ))
                                            else:
                                                # Insert a new response only if one doesn't exist
                                                cursor.execute("""
                                                    INSERT INTO Responses 
                                                    (CandidateID, Name, Mobile, JobDescription, Response, ResponseDate)
                                                    VALUES (?, ?, ?, ?, ?, ?)
                                                """, (
                                                    candidate_id,
                                                    candidate.Name,
                                                    candidate.Mobile,
                                                    candidate.JobDescription,
                                                    response_text,
                                                    datetime.now()
                                                ))
                                            conn.commit()
                                            
                                            # Send location question
                                            if send_location_question(candidate_id, candidate.Name, candidate.Mobile):
                                                print(f"Successfully recorded response and sent location question for candidate {candidate_id}")
                                            else:
                                                print(f"Failed to send location question for candidate {candidate_id}")
                                        else:
                                            print(f"No candidate found with ID {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                        conn.rollback()
                                    finally:
                                        cursor.close()
                                        conn.close()
                                
                                # In the webhook method, expand the edit response handling
                                # Edit response handling
                                elif response_id.startswith("edit_"):
                                    try:
                                        _, candidate_id, edit_field = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Handle "No, Thanks" scenario
                                    if edit_field == 'none':
                                        continue

                                    # Connect to database to get candidate details
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # Fetch candidate details
                                        cursor.execute("""
                                            SELECT Name, Mobile 
                                            FROM Responses 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Comprehensive edit options
                                            if edit_field == 'all':
                                                if send_comprehensive_edit_options(candidate_id, candidate.Name, candidate.Mobile):
                                                    print(f"Sent comprehensive edit options for candidate {candidate_id}")
                                            else:
                                                # Field-specific edit logic
                                                edit_functions = {
                                                    'location': send_location_question,
                                                    'salary': send_salary_question,
                                                    'ctc': send_expected_ctc_question,
                                                    'noticeperiod': send_notice_period_question
                                                }

                                                if edit_field in edit_functions:
                                                    edit_function = edit_functions[edit_field]
                                                    if edit_function(candidate_id, candidate.Name, candidate.Mobile):
                                                        print(f"Sent {edit_field} edit question for candidate {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                    finally:
                                        cursor.close()
                                        conn.close()

                                # Existing field-specific response handling
                                elif response_id.startswith("location_"):
                                    try:
                                        _, candidate_id, location = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Connect to database and update location response
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # Update location response
                                        cursor.execute("""
                                            UPDATE Responses
                                            SET Location = ?, LocationResponseDate = ?
                                            WHERE CandidateID = ?
                                        """, (
                                            location,
                                            datetime.now(),
                                            candidate_id
                                        ))
                                        conn.commit()
                                        
                                        # Fetch candidate info for sending next question
                                        cursor.execute("""
                                            SELECT Name, Mobile 
                                            FROM Responses 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Send salary question
                                            if send_salary_question(candidate_id, candidate.Name, candidate.Mobile):
                                                print(f"Successfully updated location and sent salary question for candidate {candidate_id}")
                                            else:
                                                print(f"Failed to send salary question for candidate {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                        conn.rollback()
                                    finally:
                                        cursor.close()
                                        conn.close()

                                # Salary response
                                elif response_id.startswith("salary_"):
                                    try:
                                        _, candidate_id, salary_range = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Connect to database and update salary response
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # Update salary response
                                        cursor.execute("""
                                            UPDATE Responses
                                            SET Salary = ?, SalaryResponseDate = ?
                                            WHERE CandidateID = ?
                                        """, (
                                            salary_range,
                                            datetime.now(),
                                            candidate_id
                                        ))
                                        conn.commit()
                                        
                                        # Fetch candidate info for sending next question
                                        cursor.execute("""
                                            SELECT Name, Mobile 
                                            FROM Responses 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Send expected CTC question
                                            if send_expected_ctc_question(candidate_id, candidate.Name, candidate.Mobile):
                                                print(f"Successfully updated salary and sent expected CTC question for candidate {candidate_id}")
                                            else:
                                                print(f"Failed to send expected CTC question for candidate {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                        conn.rollback()
                                    finally:
                                        cursor.close()
                                        conn.close()

                                # Expected CTC response
                                elif response_id.startswith("expectedctc_"):
                                    try:
                                        _, candidate_id, expected_ctc = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Connect to database and update expected CTC response
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # Update expected CTC response
                                        cursor.execute("""
                                            UPDATE Responses
                                            SET ExpectedCTC = ?, ExpectedCTCResponseDate = ?
                                            WHERE CandidateID = ?
                                        """, (
                                            expected_ctc,
                                            datetime.now(),
                                            candidate_id
                                        ))
                                        conn.commit()
                                        
                                        # Fetch candidate info for sending next question
                                        cursor.execute("""
                                            SELECT Name, Mobile 
                                            FROM Responses 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Send Notice Period question
                                            if send_notice_period_question(candidate_id, candidate.Name, candidate.Mobile):
                                                print(f"Successfully updated expected CTC and sent Notice Period question for candidate {candidate_id}")
                                            else:
                                                print(f"Failed to send Notice Period question for candidate {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                        conn.rollback()
                                    finally:
                                        cursor.close()
                                        conn.close()

                                elif response_id.startswith("noticeperiod_"):
                                    try:
                                        _, candidate_id, notice_period = response_id.split('_')
                                        candidate_id = int(candidate_id)
                                    except (ValueError, IndexError):
                                        print(f"Invalid response_id format: {response_id}")
                                        continue

                                    # Connect to database and update Notice Period response
                                    conn = pyodbc.connect(connection_string)
                                    cursor = conn.cursor()

                                    try:
                                        # Update Notice Period response
                                        cursor.execute("""
                                            UPDATE Responses
                                            SET NoticePeriod = ?, NoticePeriodResponseDate = ?
                                            WHERE CandidateID = ?
                                        """, (
                                            notice_period,
                                            datetime.now(),
                                            candidate_id
                                        ))
                                        conn.commit()
                                        
                                        # Fetch candidate details to send resume request
                                        cursor.execute("""
                                            SELECT Name, Mobile 
                                            FROM Responses 
                                            WHERE CandidateID = ?
                                        """, (candidate_id,))
                                        
                                        candidate = cursor.fetchone()
                                        
                                        if candidate:
                                            # Send resume request
                                            if send_resume_request(candidate_id, candidate.Name, candidate.Mobile):
                                                print(f"Successfully updated Notice Period and sent resume request for candidate {candidate_id}")
                                            else:
                                                print(f"Failed to send resume request for candidate {candidate_id}")
                                    
                                    except Exception as db_error:
                                        print(f"Database error: {str(db_error)}")
                                        conn.rollback()
                                    finally:
                                        cursor.close()
                                        conn.close()
                                    

            return jsonify({"status": "Webhook processed successfully"}), 200

        except Exception as e:
            print(f"Error processing webhook: {str(e)}")
            return jsonify({"error": str(e)}), 500
# Other routes remain the same
@app.route('/responses', methods=['GET'])
def get_responses():
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch all responses from the database
        cursor.execute("""
            SELECT 
                CandidateID, Name, Mobile, JobDescription, 
                Response, Location, Salary, ExpectedCTC, NoticePeriod,ResponseDate,
                CASE WHEN ResumeFileData IS NOT NULL THEN 'Yes' ELSE 'No' END as ResumeUploaded
            FROM Responses
        """)
        responses = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

        print("Fetched responses:", responses)  # Debugging log
        return jsonify(responses), 200
    except Exception as e:
        print("Error fetching responses:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/candidate-responses', methods=['POST'])
def get_candidate_responses():
    try:
        data = request.json
        candidateId = data.get('candidateId')

        if not candidateId:
            return jsonify({"error": "Failed to fetch candidate response"}), 400
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch all responses from the database
        cursor.execute("SELECT CandidateID, Name, Mobile, JobDescription, Response, Location, Salary, ExpectedCTC, NoticePeriod, ResponseDate, CASE WHEN ResumeFileData IS NOT NULL THEN 'Yes' ELSE 'No' END as ResumeUploaded FROM Responses WHERE CandidateID = ?",
            (candidateId)
        )
        responses = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

        print("Fetched responses:", responses)  # Debugging log
        return jsonify(responses), 200
    except Exception as e:
        print("Error fetching responses:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/candidate-id', methods=['POST'])
def get_candidate_id():
    try:
        data = request.json
        userId = data.get('userId')
        shortlistId = data.get('shortlistId')

        if not shortlistId:
            return jsonify({"error": "Failed to fetch candidate Id"}), 400
        
        if not userId:
            return jsonify({"error": "Failed to fetch candidate Id"}), 400
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()

        # Fetch all responses from the database
        cursor.execute("SELECT CandidateID FROM Candidates WHERE ShortlistID = ? AND UserID = ?",
            (shortlistId, userId)
        )
        responses = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

        print("Fetched responses:", responses)  # Debugging log
        return jsonify(responses), 200
    except Exception as e:
        print("Error fetching responses:", str(e))
        return jsonify({"error": str(e)}), 500


def send_location_question(candidate_id, name, mobile):
    """
    Send location question as an interactive message
    """
    message = {
        "messaging_product": "whatsapp",
        "to": f"{mobile}",
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": "Thanks for the response. Please answer the below question:\n\nCurrent Location?"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"location_{candidate_id}_bangalore", "title": "Bangalore"}},
                    {"type": "reply", "reply": {"id": f"location_{candidate_id}_hyderabad", "title": "Hyderabad"}},
                    {"type": "reply", "reply": {"id": f"location_{candidate_id}_other", "title": "Other"}}
                ]
            }
        }
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.post(whatsapp_api_url, json=message, headers=headers)
    return response.status_code == 200

if __name__ == '__main__':
    # Use PORT environment variable if available (for Azure)
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
