"""
Utility functions for the Lost & Found Portal
Includes email, PDF generation, and fuzzy matching
"""

import json
import difflib
from io import BytesIO
from datetime import datetime
from flask import Flask, Response
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from config import FUZZY_MATCH_THRESHOLD


def fuzzy_match(str1, str2, threshold=FUZZY_MATCH_THRESHOLD):
    """
    Perform fuzzy string matching using SequenceMatcher
    
    Args:
        str1: First string to compare
        str2: Second string to compare
        threshold: Similarity threshold (0.0-1.0)
    
    Returns:
        Boolean indicating if strings match above threshold
    """
    if not str1 or not str2 or len(str1) < 3 or len(str2) < 3:
        return False
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio() > threshold


def find_potential_matches(returned_found_items, query_db):
    """
    Find potential matches between lost and found items using fuzzy matching
    
    Args:
        returned_found_items: List of found items to match
        query_db: Database query function
    
    Returns:
        Sorted list of potential matches with scores
    """
    lost_items = query_db("SELECT * FROM items WHERE type='Lost' AND status='pending'")
    matches = []
    
    for found in returned_found_items:
        f_text = f"{found.get('item_name', '')} {found.get('description', '')} {found.get('location', '')}".strip()
        if not f_text:
            continue
        
        for l in lost_items:
            l_text = f"{l.get('item_name', '')} {l.get('description', '')} {l.get('location', '')}".strip()
            if fuzzy_match(l_text, f_text):
                # Parse image_urls JSON
                if l.get('image_urls'):
                    l['image_urls_list'] = json.loads(l['image_urls'])
                else:
                    l['image_urls_list'] = []
                if found.get('image_urls'):
                    found['image_urls_list'] = json.loads(found['image_urls'])
                else:
                    found['image_urls_list'] = []
                
                matches.append({
                    "lost": l,
                    "found": found,
                    "score": difflib.SequenceMatcher(None, l_text.lower(), f_text.lower()).ratio()
                })
    
    return sorted(matches, key=lambda x: x['score'], reverse=True)


def send_email(to_email, subject, body, mail_instance):
    """
    Send email using Flask-Mail
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        mail_instance: Flask-Mail instance
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not to_email:
        return False, "No recipient email"
    
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail_instance.send(msg)
        return True, "Sent"
    except Exception as e:
        return False, str(e)


def get_safe_img_url(url):
    """
    Convert .avif image URLs to .png for better compatibility
    
    Args:
        url: Image URL string
    
    Returns:
        Modified URL or original if not .avif
    """
    if url and isinstance(url, str) and '.avif' in url.lower():
        url = url.replace('/v', '/f_png/v').replace('.avif', '.png')
    return url


def generate_pdf_report(pending_lost, pending_found, matched_count, total_lost, 
                       total_found, returned_found, pending_lost_items, 
                       pending_found_items, handled_matches, query_db):
    """
    Generate a PDF report of Lost & Found statistics
    
    Args:
        Various statistics and item lists from database
        query_db: Database query function
    
    Returns:
        Response object with PDF file
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("Lost & Found Report - AIML Department", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Statistics Table
    stats_data = [
        ['Metric', 'Count'],
        ['Pending Lost', pending_lost],
        ['Pending Found', pending_found],
        ['Matched Items', matched_count],
        ['Total Lost', total_lost],
        ['Total Found', total_found],
        ['Handled Found', returned_found]
    ]
    stats_table = Table(stats_data, colWidths=[3*inch, 1*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 24))
    
    # Pending Lost Items Table
    lost_header = Paragraph("Pending Lost Items (Top 10)", styles['Heading2'])
    story.append(lost_header)
    lost_data = [['ID', 'Image', 'Name', 'Description', 'Location', 'User']]
    
    for item in pending_lost_items:
        desc_para = Paragraph(item['description'], styles['Normal'])
        img_url = None
        if item['image_urls']:
            try:
                urls = json.loads(item['image_urls'])
                if urls:
                    img_url = urls[0]
            except json.JSONDecodeError:
                pass
        
        img_url = get_safe_img_url(img_url)
        img_cell = None
        if img_url:
            try:
                img = Image(img_url, width=0.8*inch, height=0.8*inch)
                img.hAlign = 'CENTER'
                img_cell = img
            except:
                img_cell = Paragraph('No Image', styles['Normal'])
        else:
            img_cell = Paragraph('No Image', styles['Normal'])
        
        lost_data.append([str(item['id']), img_cell, item['item_name'], desc_para, 
                         item['location'], item['user_email']])
    
    lost_table = Table(lost_data, colWidths=[0.5*inch, 0.8*inch, 1.2*inch, 2.5*inch, 1.5*inch, 1.5*inch])
    lost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
    ]))
    story.append(lost_table)
    story.append(Spacer(1, 24))
    
    # Pending Found Items Table
    found_header = Paragraph("Pending Found Items (Top 10)", styles['Heading2'])
    story.append(found_header)
    found_data = [['ID', 'Image', 'Name', 'Description', 'Location', 'User']]
    
    for item in pending_found_items:
        desc_para = Paragraph(item['description'], styles['Normal'])
        img_url = None
        if item['image_urls']:
            try:
                urls = json.loads(item['image_urls'])
                if urls:
                    img_url = urls[0]
            except json.JSONDecodeError:
                pass
        
        img_url = get_safe_img_url(img_url)
        img_cell = None
        if img_url:
            try:
                img = Image(img_url, width=0.8*inch, height=0.8*inch)
                img.hAlign = 'CENTER'
                img_cell = img
            except:
                img_cell = Paragraph('No Image', styles['Normal'])
        else:
            img_cell = Paragraph('No Image', styles['Normal'])
        
        found_data.append([str(item['id']), img_cell, item['item_name'], desc_para, 
                          item['location'], item['user_email']])
    
    found_table = Table(found_data, colWidths=[0.5*inch, 0.8*inch, 1.2*inch, 2.5*inch, 1.5*inch, 1.5*inch])
    found_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
    ]))
    story.append(found_table)
    story.append(Spacer(1, 24))
    
    # Handled Matches Table
    handled_header = Paragraph("Handled Matches (Top 10)", styles['Heading2'])
    story.append(handled_header)
    handled_data = [['ID', 'Lost Img', 'Lost Item', 'Lost Contact', 'Found Img', 'Found Item', 'Found Contact', 'Status']]
    
    for match in handled_matches:
        lost_desc_short = match['lost_desc'][:50] + '...' if len(match['lost_desc']) > 50 else match['lost_desc']
        found_desc_short = match['found_desc'][:50] + '...' if len(match['found_desc']) > 50 else match['found_desc']
        
        lost_item_para = Paragraph(f"<b>{match['lost_name']}</b><br/><i>{lost_desc_short}</i>", styles['Normal'])
        found_item_para = Paragraph(f"<b>{match['found_name']}</b><br/><i>{found_desc_short}</i>", styles['Normal'])
        
        lost_contact_para = Paragraph(f"{match['lost_email']} / {match.get('lost_phone', 'N/A')}", styles['Normal'])
        found_contact_para = Paragraph(f"{match['found_email']} / {match.get('found_phone', 'N/A')}", styles['Normal'])
        
        # Process images
        lost_img_url = None
        if match['lost_images']:
            try:
                urls = json.loads(match['lost_images'])
                if urls:
                    lost_img_url = urls[0]
            except json.JSONDecodeError:
                pass
        
        lost_img_url = get_safe_img_url(lost_img_url)
        lost_img_cell = None
        if lost_img_url:
            try:
                img = Image(lost_img_url, width=0.5*inch, height=0.5*inch)
                img.hAlign = 'CENTER'
                lost_img_cell = img
            except:
                lost_img_cell = Paragraph('Img', styles['Normal'])
        else:
            lost_img_cell = Paragraph('Img', styles['Normal'])
        
        found_img_url = None
        if match['found_images']:
            try:
                urls = json.loads(match['found_images'])
                if urls:
                    found_img_url = urls[0]
            except json.JSONDecodeError:
                pass
        
        found_img_url = get_safe_img_url(found_img_url)
        found_img_cell = None
        if found_img_url:
            try:
                img = Image(found_img_url, width=0.5*inch, height=0.5*inch)
                img.hAlign = 'CENTER'
                found_img_cell = img
            except:
                found_img_cell = Paragraph('Img', styles['Normal'])
        else:
            found_img_cell = Paragraph('Img', styles['Normal'])
        
        handled_data.append([
            str(match['match_id']),
            lost_img_cell,
            lost_item_para,
            lost_contact_para,
            found_img_cell,
            found_item_para,
            found_contact_para,
            match['status']
        ])
    
    handled_table = Table(handled_data, colWidths=[0.4*inch, 0.5*inch, 1.2*inch, 1.0*inch, 0.5*inch, 1.2*inch, 1.0*inch, 0.7*inch])
    handled_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
    ]))
    story.append(handled_table)
    
    doc.build(story)
    buffer.seek(0)
    
    response = Response(buffer.getvalue(), mimetype='application/pdf')
    response.headers['Content-Disposition'] = 'attachment; filename=lf_report.pdf'
    return response


def get_base_style(page_key):
    """
    Return CSS styling for different pages
    
    Args:
        page_key: Page type (auth, home, dashboard, view)
    
    Returns:
        CSS string for the page
    """
    if page_key == "auth":
        bg = "linear-gradient(135deg, #ff6ec7 0%, #7b2ff7 50%, #00c6ff 100%)"
    elif page_key == "home":
        bg = "linear-gradient(135deg, #ff6ec7 0%, #7b2ff7 50%, #00c6ff 100%)"
    elif page_key == "dashboard":
        bg = "linear-gradient(135deg, #ff6ec7 0%, #7b2ff7 45%, #00c6ff 100%)"
    elif page_key == "view":
        bg = "linear-gradient(135deg, #ff9a9e 0%, #fad0c4 50%, #7b2ff7 100%)"
    else:
        bg = "linear-gradient(135deg, #ff6ec7 0%, #7b2ff7 50%, #00c6ff 100%)"
    
    return f"""
<style>
:root {{ --bg-grad: {bg}; }}
html, body {{ height:100%; margin:0; }}
body {{
  font-family: 'Roboto', Arial, sans-serif;
  margin:0; padding:0;
  background: var(--bg-grad);
  background-attachment: fixed;
  color:#222;
  min-height:100vh;
  display:flex;
  align-items:flex-start;
  justify-content:center;
  padding:24px;
}}
.bg-overlay {{ background: rgba(255,255,255,0.06); backdrop-filter: blur(6px); position:fixed; inset:0; z-index:-1; }}
.container {{ width:100%; max-width:1100px; }}
.main {{
  max-width:1100px; margin:40px auto 0 auto; padding:24px;
  background:rgba(255,255,255,0.92);
  border-radius:18px; box-shadow:0 8px 40px rgba(0,0,0,0.12);
}}
.navbar {{ background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.07); padding: 0 20px; height:64px; display:flex; align-items:center; justify-content:space-between; border-radius:12px; }}
.navbar .logo {{ font-size:1.4rem; font-weight:700; color:#6a11cb; letter-spacing:1px; }}
.navbar .user {{ font-size:1rem; color:#555; }}
.navbar .notif {{ font-size:2rem; color:#6a11cb; margin-right:18px; cursor:pointer; position:relative; text-decoration:none; display:flex; align-items:center; gap:8px; font-weight:600; }}
.navbar .notif .badge {{ position:absolute; top:-6px; right:-8px; background:#d32f2f; color:#fff; border-radius:50%; font-size:0.8rem; padding:2px 7px; min-width:18px; height:18px; display:flex; align-items:center; justify-content:center; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:24px; margin-top:32px; align-items:start; }}
.card {{ background:#fff; border-radius:14px; box-shadow:0 4px 16px rgba(0,0,0,0.08); padding:20px; transition:0.3s all; position:relative; min-height:280px; overflow:hidden; display:flex; flex-direction:column; }}
.card:hover {{ transform:translateY(-4px); box-shadow:0 8px 32px rgba(106,17,203,0.15); }}
.card img {{ max-width:100%; max-height:120px; object-fit:cover; border-radius:8px; margin-top:auto; }}
.card .type {{ position:absolute; top:12px; right:12px; font-size:0.85rem; font-weight:600; padding:6px 12px; border-radius:20px; }}
.card.lost .type {{ background:#ffebee; color:#d32f2f; }}
.card.found .type {{ background:#e8f5e9; color:#388e3c; }}
.card.pending .type {{ background:#fff3e0; color:#f57c00; }}
.card.returned .type {{ background:#e8f5e9; color:#388e3c; }}
.card.matched .type {{ background:#e8f5e9; color:#388e3c; }}
.card.collected .type {{ background:#e3f2fd; color:#1976d2; }}
.btn {{ padding:10px 22px; border-radius:8px; font-weight:600; text-decoration:none; margin:8px 0; cursor:pointer; border:none; background:linear-gradient(90deg,#7b2ff7,#00c6ff); color:#fff; transition:0.25s; font-size:1.05rem; }}
.btn:hover {{ transform:translateY(-2px); opacity:0.95; }}
.btn.reject {{ background:linear-gradient(90deg,#ff8a65,#ff5252); }}
.btn.approve {{ background:linear-gradient(90deg,#a5d6a7,#388e3c); }}
.btn.return {{ background:linear-gradient(90deg,#e3f2fd,#bbdefb); color:#1976d2; }}
.btn.view {{ background:linear-gradient(90deg,#64b5f6,#1976d2); }}
input, textarea {{ width:100%; padding:8px; margin:5px 0; border-radius:6px; border:1px solid #e0e0e0; background:#fafafa; color:#222; box-sizing:border-box; font-size:0.95rem; }}
input:focus, textarea:focus {{ border-color:#7b2ff7; box-shadow:0 0 6px rgba(123,47,247,0.12); outline:none; }}
textarea {{ resize:vertical; min-height:60px; }}
.form-compact {{ margin:0; padding:0; }}
.form-compact > * {{ margin:0 0 8px 0; }}
.footer {{ text-align:center; padding:18px; color:#555; font-size:0.95rem; margin-top:40px; }}
.edit-delete {{ position:absolute; top:12px; left:12px; display:flex; gap:8px; }}
.edit-delete a {{ font-size:1.1rem; padding:4px 8px; border-radius:6px; text-decoration:none; transition:0.2s; background:#f3f3f3; color:#6a11cb; }}
.edit-delete a:hover {{ background:#e3f2fd; }}
.card-stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:32px; }}
.stat-card {{ background:linear-gradient(90deg,#f3e8ff,#e0f7ff); color:#6a11cb; text-align:center; padding:20px; border-radius:12px; font-weight:700; box-shadow:0 4px 12px rgba(106,17,203,0.08); transition:0.3s; cursor:pointer; }}
.stat-card:hover {{ transform:translateY(-4px); box-shadow:0 8px 24px rgba(106,17,203,0.15); }}
.stat-card.lost {{ background:linear-gradient(90deg,#ffebee,#ffcdd2); color:#d32f2f; }}
.stat-card.found {{ background:linear-gradient(90deg,#e8f5e9,#c8e6c9); color:#388e3c; }}
.stat-card.pending {{ background:linear-gradient(90deg,#fff3e0,#ffe0b2); color:#f57c00; }}
.stat-card.match {{ background:linear-gradient(90deg,#fffde7,#fff9c4); color:#fbc02d; }}
.stat-card .icon {{ font-size:2.5rem; display:block; margin-bottom:12px; }}
.stat-card h3 {{ font-size:1.2rem; margin:0 0 8px 0; opacity:0.8; }}
.stat-card .count {{ font-size:2.8rem; font-weight:900; line-height:1; }}
.quick_actions {{ display:flex; flex-wrap:wrap; gap:16px; margin-bottom:32px; justify-content:center; }}
.dashboard_header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }}
.dashboard_header h2 {{ color:#6a11cb; font-size:2.2rem; font-weight:800; margin:0; }}
.dashboard_header .college {{ font-size:1.1rem; color:#388e3c; font-weight:600; }}
.match_card {{ background:#fff; border-radius:14px; box-shadow:0 2px 12px rgba(0,0,0,0.07); padding:22px; margin-bottom:20px; }}
.match_actions {{ display:flex; gap:12px; margin-top:12px; }}
.pending_matches {{ background:rgba(255,255,255,0.92); padding:20px; border-radius:12px; margin:20px 0; }}
.images-row {{
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 10px 0;
  border-top: 1px solid #eee;
  margin-top: auto;
}}
.thumbnail {{
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  flex-shrink: 0;
}}
.match-images {{
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: 10px 0;
}}
.match-images .images-row {{
  flex: 1;
  border-top: none;
  padding: 0;
}}
.match-label {{
  font-weight: 500;
  font-size: 0.9em;
  color: #666;
  margin-bottom: 5px;
}}
.admin-notifs {{ background:#fff3e0; padding:12px; border-radius:8px; margin:16px 0; }}
.admin-notif {{ padding:8px; border-bottom:1px solid #eee; font-size:0.9rem; }}
.admin-notif:last-child {{ border-bottom:none; }}
.match-preview {{
  background: #f0f8ff;
  border-left: 3px solid #388e3c;
  padding: 8px;
  margin-top: 8px;
  border-radius: 4px;
  font-size: 0.85rem;
}}
.match-preview h5 {{ margin: 0 0 4px 0; font-size: 0.9rem; color: #388e3c; }}
.match-preview small {{ color: #666; }}
@media (max-width:700px) {{
  .main {{ padding:12px; border-radius:12px; margin-top:20px; }}
  .card-grid {{ grid-template-columns:1fr; gap:16px; }}
  .navbar {{ padding:0 12px; height:56px; }}
  .match_actions {{ flex-direction:column; }}
  .quick_actions {{ flex-direction:column; align-items:center; }}
  .card {{ padding:16px; min-height:260px; }}
  .dashboard_header {{ flex-direction:column; gap:8px; text-align:center; }}
  .thumbnail {{ width: 60px; height: 60px; }}
  .match-images {{ flex-direction: column; }}
}}
.report-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
.report-stat {{ background: #f9f9f9; padding: 20px; border-radius: 10px; text-align: center; border-left: 4px solid #6a11cb; }}
.report-stat h3 {{ margin: 0 0 10px 0; color: #6a11cb; }}
.report-stat .count {{ font-size: 2rem; font-weight: bold; color: #388e3c; }}
.download-btn {{ display: block; margin: 20px auto; padding: 12px 24px; background: linear-gradient(90deg, #388e3c, #4caf50); color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }}
</style>
<div class="bg-overlay"></div>
"""
