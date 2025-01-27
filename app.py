from io import BytesIO
import PyPDF2
from flask import Flask, render_template, request
from openai import APIError, OpenAI , RateLimitError
import docx
import os
from dotenv import load_dotenv
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4

# Ensure you're loading the environment variable correctly
load_dotenv()

app = Flask(__name__)

# Initialize OpenAI client

client = OpenAI(
    api_key="DEEPSEEK_API_KEY",
    base_url="https://api.deepseek.com"
)

def extract_text_from_resume(resume_file):
    """Extract text from PDF or DOCX resume file."""
    if resume_file.filename.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(BytesIO(resume_file.read()))
        return ' '.join(page.extract_text() for page in pdf_reader.pages)
    
    elif resume_file.filename.endswith('.docx'):
        doc = docx.Document(BytesIO(resume_file.read()))
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    
    raise ValueError("Unsupported file format. Please upload a PDF or DOCX file.")

def optimize_resume(job_description, resume_text):
   """Optimize resume using the Deepseek API."""
   try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert ATS resume optimizer and professional resume formatter. 
                    Your specific tasks are:
                    1. Format must be EXACTLY one A4 page (no exceptions)
                    2. Use this exact formatting:
                       - Name in bold and centered, 12pt
                       - Section headers in bold, 10pt
                       - Body text 9-10pt
                       - Margins 0.75 inches/1.9cm all sides
                       - Single line spacing with 4pt spacing between sections
                    3. Optimize content for ATS matching
                    4. Keep only the most relevant information that fits in one page
                    5. Must maintain the professional formatting with:
                       - Bold headings for all sections
                       - Consistent bullet points
                       - Clear section divisions but no strokes 
                       - Tight but readable spacing
                    FORMAT THE OUTPUT TO FIT EXACTLY ONE A4 PAGE - THIS IS CRUCIAL"""
                },
                {
                    "role": "user",
                    "content": f"Job Description for ATS Optimization:\n{job_description}"
                },
                {
                    "role": "user", 
                    "content": f"Resume to be optimized and formatted:\n{resume_text}"
                },
                {
                    "role": "user",
                    "content": """Format this resume to fit EXACTLY one A4 page with:
                    1. Bold and centered name at top
                    2. Bold section headings
                    3. Professional bullet points
                    4. Minimal but clear section spacing
                    5. Perfect one-page A4 fit"""
                }
            ],
            stream=False
        )
        
        return response.choices[0].message.content

   except RateLimitError:
       raise Exception("Service is currently busy. Please try again in a few minutes.")
   except APIError as e:
       if 'Insufficient Balance' in str(e):
           raise Exception("Service temporarily unavailable. Please try again later.")
       raise Exception(f"API Error: {str(e)}")
   except Exception as e:
       raise Exception(f"Error optimizing resume: {str(e)}")

@app.route('/')
def index():
    """Render the landing page."""
    return render_template('index.html')

@app.route('/resume_optimiser', methods=['GET', 'POST'])
def resume_optimiser_page():
    """Handle resume optimization requests."""
    if request.method != 'POST':
        return render_template('resume_optimiser.html')

    # Get form data
    job_description = request.form.get('job_description', '')
    resume_file = request.files.get('resume')

    # Validate inputs
    if not resume_file or not job_description:
        return render_template(
            'resume_optimiser.html',
            error="Please provide both job description and resume file."
        )

    try:
        # Process resume file
        resume_text = extract_text_from_resume(resume_file)
        
        # Get optimized resume
        optimized_resume = optimize_resume(job_description, resume_text)

        return render_template(
            'resume_optimiser.html',
            optimized_resume=optimized_resume,
            job_description=job_description,
            original_resume=resume_text
        )

    except ValueError as e:
        return render_template('resume_optimiser.html', error=str(e))
    
    except Exception as e:
        return render_template(
            'resume_optimiser.html',
            error=f"An error occurred: {str(e)}"
        )



from flask import send_file
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

@app.route('/view', methods=['POST'])
def view_as_html():
    """Handle HTML view of resume."""
    try:
        optimized_resume = request.form.get('optimized_resume', '')
        
        # Remove the formatting notes line
        lines = [line for line in optimized_resume.split('\n') 
                 if not line.startswith('This resume is formatted')]
        
        formatted_lines = []
        
        for line in lines:
            # Replace bullet points
            line = line.replace('•', '<li>')
            
            # Handle double asterisks (bold)
            while '**' in line:
                line = line.replace('**', '<strong>', 1)
                line = line.replace('**', '</strong>', 1)
            
            # Handle section headings
            if line.isupper() and line.strip():
                line = f'<div class="section-header">{line}</div>'
            
            # Handle job/project titles
            if line.startswith('<strong>') and '|' in line:
                line = f'<div class="job-title">{line}</div>'
            
            # Wrap bullet points in ul
            if line.startswith('<li>'):
                line = f'<ul class="bullet-points">{line}</ul>'
            
            # Skip empty lines
            if line.strip():
                formatted_lines.append(line)
        
        # Find the name (first line with contact info)
        name_line = lines[0].split('|')[0].strip()
        contact_info = ' | '.join(lines[0].split('|')[1:]).strip()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Lincoln Tangirai Chanakira - Resume</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 21cm;
                    margin: 0 auto;
                    padding: 1.9cm;
                    line-height: 1.4;
                    color: #333;
                    font-size: 11pt;
                }}
                .name {{
                    font-size: 16pt;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 10px;
                }}
                .contact-info {{
                    text-align: center;
                    font-size: 10pt;
                    margin-bottom: 20px;
                }}
                .section-header {{
                    font-size: 12pt;
                    font-weight: bold;
                    margin-top: 15px;
                    margin-bottom: 10px;
                    text-transform: uppercase;
                    border-bottom: 2px solid #000;
                    padding-bottom: 5px;
                }}
                .job-title {{
                    font-weight: bold;
                    margin-bottom: 5px;
                }}
                .bullet-points {{
                    margin-left: 20px;
                    margin-bottom: 15px;
                }}
                .bullet-points li {{
                    margin-bottom: 5px;
                }}
                strong {{
                    font-weight: bold;
                }}
                @media print {{
                    body {{
                        padding: 0;
                        margin: 1.9cm;
                    }}
                    @page {{
                        size: A4;
                        margin: 0;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="name">{name_line}</div>
            <div class="contact-info">{contact_info}</div>
            
            <div class="content">
                {''.join(formatted_lines)}
            </div>
        </body>
        </html>
        """
        
        response = app.response_class(
            html_content,
            mimetype='text/html'
        )
        
        return response
    except Exception as e:
        return render_template(
            'resume_optimiser.html',
            error=f"An error occurred during view: {str(e)}"
        )

@app.route('/download_pdf')
def download_pdf():
    """Generate and download the optimized resume as PDF."""
    try:
        content = request.args.get('content', '')
        
        # Remove formatting notes line
        content_lines = [line for line in content.split('\n') 
                         if not line.startswith('This resume is formatted')]
        content = '\n'.join(content_lines)
        
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.9*cm,
            leftMargin=1.9*cm,
            topMargin=1.9*cm,
            bottomMargin=1.9*cm
        )
        
        # Create styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='Name',
            fontSize=12,
            alignment=1,  # Center
            spaceAfter=12,
            bold=True
        ))
        styles.add(ParagraphStyle(
            name='Heading',
            fontSize=10,
            spaceAfter=6,
            spaceBefore=8,
            bold=True
        ))
        styles.add(ParagraphStyle(
            name='Body',
            fontSize=9,
            leading=11,
            spaceAfter=3
        ))
        
        # Parse content and apply styles
        story = []
        lines = content.split('\n')
        is_first_line = True
        
        for line in lines:
            if not line.strip():
                continue
                
            if is_first_line:
                # First line is the name
                story.append(Paragraph(line.replace('*', ''), styles['Name']))
                is_first_line = False
            elif line.strip().isupper() or line.startswith('**'):
                # Section headers
                clean_line = line.replace('*', '').strip()
                story.append(Paragraph(clean_line, styles['Heading']))
            else:
                # Regular content
                if line.strip().startswith('•') or line.strip().startswith('-'):
                    # Handle bullet points with proper indentation
                    line = f"    • {line.strip()[1:].strip()}"
                story.append(Paragraph(line, styles['Body']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name='optimized_resume.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return render_template('resume_optimiser.html', error=f"PDF generation failed: {str(e)}")
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host= '0.0.0.0', port=port)