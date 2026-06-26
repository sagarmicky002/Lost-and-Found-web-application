"""
Lost & Found Portal - Flask Application
Routes and main application logic
"""

import os
import json
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail

# Import configurations and utilities
from config import (
    FLASK_SECRET, CLOUDINARY_CONFIG, DB_CONFIG, MAIL_SERVER, MAIL_PORT,
    MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER
)
from db import query_db, init_db
from utils import (
    send_email, fuzzy_match, find_potential_matches, get_safe_img_url,
    get_base_style, generate_pdf_report
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = FLASK_SECRET

# Configure Flask-Mail
app.config["MAIL_SERVER"] = MAIL_SERVER
app.config["MAIL_PORT"] = MAIL_PORT
app.config["MAIL_USE_TLS"] = MAIL_USE_TLS
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD
app.config["MAIL_DEFAULT_SENDER"] = MAIL_DEFAULT_SENDER
mail = Mail(app)

# Configure Cloudinary
cloudinary.config(**CLOUDINARY_CONFIG)

# Initialize database
init_db()


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            flash("Username and password required.")
            return render_template_string(get_base_style("auth") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
</div>
<div class='main' style='max-width:440px;margin-top:80px;'>
  <h2>Admin Login</h2>
  <form method="POST" autocomplete="off">
    <input name="username" placeholder="Username" required autocomplete="new-username"><br>
    <input name="password" type="password" placeholder="Password" required autocomplete="new-password"><br>
    <button class="btn" type="submit">Login</button>
  </form>
  <p style="margin-top:12px;"><a href="{{ url_for('welcome') }}">← Back to site</a></p>
  {% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
</div>
""")
        
        admin = query_db("SELECT * FROM admin WHERE username=%s", (username,), fetchone=True)
        if admin:
            stored = admin.get("password") or ""
            try:
                if check_password_hash(stored, password):
                    session.clear()
                    session["admin"] = True
                    session["admin_username"] = admin["username"]
                    return redirect(url_for("admin_dashboard"))
            except ValueError:
                pass
            
            if stored == password:
                new_hashed = generate_password_hash(password)
                con = query_db.__self__.__class__.get_db() if hasattr(query_db, '__self__') else None
                from db import get_db
                con = get_db()
                cur = con.cursor()
                cur.execute("UPDATE admin SET password=%s WHERE id=%s", (new_hashed, admin["id"]))
                con.commit()
                cur.close()
                con.close()
                session.clear()
                session["admin"] = True
                session["admin_username"] = admin["username"]
                return redirect(url_for("admin_dashboard"))
        
        flash("Invalid admin credentials.")
    
    return render_template_string(get_base_style("auth") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
</div>
<div class='main' style='max-width:440px;margin-top:80px;'>
  <h2>Admin Login</h2>
  <form method="POST" autocomplete="off">
    <input name="username" placeholder="Username" required autocomplete="new-username"><br>
    <input name="password" type="password" placeholder="Password" required autocomplete="new-password"><br>
    <button class="btn" type="submit">Login</button>
  </form>
  <p style="margin-top:12px;"><a href="{{ url_for('welcome') }}">← Back to site</a></p>
  {% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
</div>
""")


@app.route("/admin_dashboard")
def admin_dashboard():
    """Admin dashboard with statistics"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    pending_returns = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found' AND status='pending'", fetchone=True)["cnt"]
    pending_matches_count = query_db("SELECT COUNT(*) as cnt FROM matches WHERE status='pending'", fetchone=True)["cnt"]
    total_lost = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Lost'", fetchone=True)["cnt"]
    total_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found'", fetchone=True)["cnt"]
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
  <span style="display:flex;align-items:center;">
    <span class='user'>Admin: {{ session.get('admin_username') }} | <a href="{{ url_for('admin_logout') }}" class="btn" style="background:#444;">Logout</a></span>
  </span>
</div>
<div class='main'>
  <div class="dashboard-header">
    <h2>Admin Dashboard</h2>
    <span class="college">AIML Department</span>
  </div>
  <div class="card-stats">
    <a href="{{ url_for('admin_returns') }}" class="stat-card pending">
      <span class="icon">📦</span>
      <h3>Pending Returns</h3>
      <div class="count">{{ pending_returns }}</div>
    </a>
    <a href="{{ url_for('admin_matches') }}" class="stat-card match">
      <span class="icon">🤝</span>
      <h3>Pending Matches</h3>
      <div class="count">{{ pending_matches_count }}</div>
    </a>
    <a href="{{ url_for('admin_full_view', tab='lost') }}" class="stat-card lost">
      <span class="icon">🛑</span>
      <h3>Total Lost</h3>
      <div class="count">{{ total_lost }}</div>
    </a>
    <a href="{{ url_for('admin_full_view', tab='found') }}" class="stat-card found">
      <span class="icon">🔍</span>
      <h3>Total Found</h3>
      <div class="count">{{ total_found }}</div>
    </a>
  </div>
  <div class="quick-actions">
    <a href="{{ url_for('admin_returns') }}" class="btn approve">Manage Returns</a>
    <a href="{{ url_for('admin_matches') }}" class="btn match">Manage Matches</a>
    <a href="{{ url_for('admin_full_view') }}" class="btn view">View All Items</a>
    <a href="{{ url_for('admin_report') }}" class="btn" style="background:linear-gradient(90deg,#ff9800,#ffc107);">Generate Report</a>
  </div>
</div>
<div class='footer'>© 2025 Lost & Found Portal (Admin)</div>
</div>
""", pending_returns=pending_returns, pending_matches_count=pending_matches_count, total_lost=total_lost, total_found=total_found)


@app.route("/admin_report")
def admin_report():
    """Admin report page with statistics"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    pending_lost = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Lost' AND status='pending'", fetchone=True)["cnt"]
    pending_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found' AND status='pending'", fetchone=True)["cnt"]
    matched_count = query_db("SELECT COUNT(*) as cnt FROM matches WHERE status IN ('approved', 'collected')", fetchone=True)["cnt"]
    total_lost = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Lost'", fetchone=True)["cnt"]
    total_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found'", fetchone=True)["cnt"]
    returned_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found' AND status IN ('returned', 'matched', 'collected')", fetchone=True)["cnt"]
    
    pending_lost_items = query_db("SELECT id, item_name, description, location, user_email FROM items WHERE type='Lost' AND status='pending' ORDER BY id DESC LIMIT 10")
    pending_found_items = query_db("SELECT id, item_name, description, location, user_email FROM items WHERE type='Found' AND status='pending' ORDER BY id DESC LIMIT 10")
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
  <span style="display:flex;align-items:center;">
    <a href="{{ url_for('admin_dashboard') }}" class="btn">← Back to Dashboard</a>
  </span>
</div>
<div class='main'>
  <h2>Report Overview</h2>
  <p style="margin-bottom:20px;">Current statistics (updates dynamically as items are processed).</p>
  <div class="report-stats">
    <div class="report-stat">
      <h3>Pending Lost (To Be Found)</h3>
      <div class="count">{{ pending_lost }}</div>
    </div>
    <div class="report-stat">
      <h3>Pending Found (To Be Returned)</h3>
      <div class="count">{{ pending_found }}</div>
    </div>
    <div class="report-stat">
      <h3>Matched Items</h3>
      <div class="count">{{ matched_count }}</div>
    </div>
    <div class="report-stat">
      <h3>Total Lost</h3>
      <div class="count">{{ total_lost }}</div>
    </div>
    <div class="report-stat">
      <h3>Total Found</h3>
      <div class="count">{{ total_found }}</div>
    </div>
    <div class="report-stat">
      <h3>Handled Found</h3>
      <div class="count">{{ returned_found }}</div>
    </div>
  </div>
  <a href="{{ url_for('admin_report_pdf') }}" class="download-btn">📄 Download PDF Report</a>
  <h3 style="margin-top:40px;">Recent Pending Lost Items</h3>
  <div style="overflow:auto; margin-top:10px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr style="background:#ffebee;">
        <th style="padding:10px;border:1px solid #e0e0e0;">ID</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Name</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Description</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Location</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">User</th>
      </tr>
      {% for i in pending_lost_items %}
      <tr>
        <td style="padding:8px;border:1px solid #eee;">{{ i['id'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['item_name'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['description'][:50] }}...</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['location'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['user_email'] }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
  <h3 style="margin-top:40px;">Recent Pending Found Items</h3>
  <div style="overflow:auto; margin-top:10px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr style="background:#e8f5e9;">
        <th style="padding:10px;border:1px solid #e0e0e0;">ID</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Name</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Description</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Location</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">User</th>
      </tr>
      {% for i in pending_found_items %}
      <tr>
        <td style="padding:8px;border:1px solid #eee;">{{ i['id'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['item_name'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['description'][:50] }}...</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['location'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['user_email'] }}</td>
      </tr>
      {% endfor %}
    </table>
  </div>
</div>
<div class='footer'>© 2025 Lost & Found Portal (Admin)</div>
</div>
""", pending_lost=pending_lost, pending_found=pending_found, matched_count=matched_count, total_lost=total_lost, total_found=total_found, returned_found=returned_found, pending_lost_items=pending_lost_items, pending_found_items=pending_found_items)


@app.route("/admin_report_pdf")
def admin_report_pdf():
    """Generate PDF report"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    pending_lost = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Lost' AND status='pending'", fetchone=True)["cnt"]
    pending_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found' AND status='pending'", fetchone=True)["cnt"]
    matched_count = query_db("SELECT COUNT(*) as cnt FROM matches WHERE status IN ('approved', 'collected')", fetchone=True)["cnt"]
    total_lost = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Lost'", fetchone=True)["cnt"]
    total_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found'", fetchone=True)["cnt"]
    returned_found = query_db("SELECT COUNT(*) as cnt FROM items WHERE type='Found' AND status IN ('returned', 'matched', 'collected')", fetchone=True)["cnt"]
    
    pending_lost_items = query_db("SELECT id, item_name, description, location, user_email, image_urls FROM items WHERE type='Lost' AND status='pending' ORDER BY id DESC LIMIT 10")
    pending_found_items = query_db("SELECT id, item_name, description, location, user_email, image_urls FROM items WHERE type='Found' AND status='pending' ORDER BY id DESC LIMIT 10")
    handled_matches = query_db("""
        SELECT m.id as match_id, li.id as lost_id, li.item_name as lost_name, li.description as lost_desc, li.location as lost_loc, li.user_email as lost_email, li.phone as lost_phone, li.image_urls as lost_images,
               fi.id as found_id, fi.item_name as found_name, fi.description as found_desc, fi.location as found_loc, fi.user_email as found_email, fi.phone as found_phone, fi.image_urls as found_images,
               m.status, m.created_at
        FROM matches m
        JOIN items li ON m.lost_item_id = li.id
        JOIN items fi ON m.found_item_id = fi.id
        WHERE m.status IN ('approved', 'collected')
        ORDER BY m.created_at DESC LIMIT 10
    """)
    
    return generate_pdf_report(pending_lost, pending_found, matched_count, total_lost, 
                              total_found, returned_found, pending_lost_items, 
                              pending_found_items, handled_matches, query_db)


@app.route("/admin_full_view")
def admin_full_view():
    """View all items with filtering"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    tab = request.args.get("tab", "all")
    status_filter = request.args.get("status", "all")
    valid_statuses = ['pending', 'returned', 'matched', 'collected', 'all']
    
    if status_filter != "all" and status_filter not in valid_statuses:
        status_filter = "all"
    
    if tab == "lost" and status_filter != "all":
        items = query_db("SELECT * FROM items WHERE type='Lost' AND status=%s ORDER BY id DESC", (status_filter,))
    elif tab == "found" and status_filter != "all":
        items = query_db("SELECT * FROM items WHERE type='Found' AND status=%s ORDER BY id DESC", (status_filter,))
    elif status_filter != "all":
        items = query_db("SELECT * FROM items WHERE status=%s ORDER BY id DESC", (status_filter,))
    elif tab == "lost":
        items = query_db("SELECT * FROM items WHERE type='Lost' ORDER BY id DESC")
    elif tab == "found":
        items = query_db("SELECT * FROM items WHERE type='Found' ORDER BY id DESC")
    else:
        items = query_db("SELECT * FROM items ORDER BY id DESC")
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
  <span style="display:flex;align-items:center;">
    <a href="{{ url_for('admin_dashboard') }}" class="btn">← Back to Dashboard</a>
  </span>
</div>
<div class='main'>
  <h2>Full Items View</h2>
  <div style="overflow:auto; margin-top:20px;">
    <table style="width:100%;border-collapse:collapse;">
      <tr style="background:#6a11cb;color:#fff;">
        <th style="padding:10px;border:1px solid #e0e0e0;">ID</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Type</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Status</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Name</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">User</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Phone</th>
        <th style="padding:10px;border:1px solid #e0e0e0;">Action</th>
      </tr>
      {% for i in items %}
      <tr>
        <td style="padding:8px;border:1px solid #eee;">{{ i['id'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['type'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['status'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['item_name'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['user_email'] }}</td>
        <td style="padding:8px;border:1px solid #eee;">{{ i['phone'] or 'N/A' }}</td>
        <td style="padding:8px;border:1px solid #eee;">
          <a href="{{ url_for('admin_delete', item_id=i['id']) }}" onclick="return confirm('Delete? This will also remove related matches.')" class="btn" style="background:#d32f2f;color:#fff;padding:6px 10px;font-size:0.9rem;">Delete</a>
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>
</div>
<div class='footer'>© 2025 Lost & Found Portal (Admin)</div>
</div>
""", items=items)


@app.route("/admin_returns")
def admin_returns():
    """Manage pending item returns"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    pending_returns = query_db("SELECT * FROM items WHERE type='Found' AND status='pending' ORDER BY id DESC")
    
    for item in pending_returns:
        if item.get('image_urls'):
            item['image_urls_list'] = json.loads(item['image_urls'])
        else:
            item['image_urls_list'] = []
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
  <span style="display:flex;align-items:center;">
    <a href="{{ url_for('admin_dashboard') }}" class="btn">← Back to Dashboard</a>
  </span>
</div>
<div class='main'>
  <h2>Pending Returns</h2>
  <div class="card-grid">
    {% for item in pending_returns %}
    <div class="card found pending">
      <span class="type">Pending Return</span>
      <strong>{{ item['item_name'] }}</strong>
      <p style="margin:8px 0; line-height:1.4;">{{ item['description'] }}</p>
      <small style="color:#666;">Location: {{ item['location'] }}</small>
      {% if item['phone'] %}
      <small style="color:#666; display:block; margin-top:4px;">Phone: <b>{{ item['phone'] }}</b></small>
      {% endif %}
      {% if item['image_urls_list'] %}
        <div class="images-row">
          {% for url in item['image_urls_list'] %}
          <img src="{{ url }}" alt="Item Image" class="thumbnail">
          {% endfor %}
        </div>
      {% endif %}
      <div class="match-actions" style="margin-top:auto; padding-top:10px;">
        <a href="{{ url_for('admin_approve_return', item_id=item['id']) }}" class="btn approve">Approve Return & Notify Finder</a>
      </div>
    </div>
    {% endfor %}
  </div>
  {% if not pending_returns %}
  <p style="text-align:center; color:#666; padding:40px; font-style:italic;">No pending returns at the moment.</p>
  {% endif %}
</div>
<div class='footer'>© 2025 Lost & Found Portal (Admin)</div>
</div>
""", pending_returns=pending_returns)


@app.route("/admin_approve_return/<int:item_id>")
def admin_approve_return(item_id):
    """Approve item return"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    item = query_db("SELECT * FROM items WHERE id=%s", (item_id,), fetchone=True)
    if item and item['type'] == 'Found' and item['status'] == 'pending':
        query_db("UPDATE items SET status='returned' WHERE id=%s", (item_id,), commit=True)
        
        finder_email = item['user_email']
        subject = "Item Return Approved"
        body = f"""Hi,
Your found item '{item['item_name']}' is approved. Return to AIML admin office.
Desc: {item['description'][:100]}
Loc: {item['location']}
Phone: {item.get('phone', 'N/A')}
AIML Lost & Found."""
        
        ok, info = send_email(finder_email, subject, body, mail)
        note = f"Return approved and email to finder: {info}" if ok else f"Return approved but email failed: {info}"
        query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", (finder_email, note), commit=True)
    else:
        flash("Item not found or not pending.")
    
    return redirect(url_for("admin_returns"))


@app.route("/admin_matches")
def admin_matches():
    """Manage item matches"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    returned_found = query_db("SELECT * FROM items WHERE type='Found' AND status='returned'")
    potential_matches = find_potential_matches(returned_found, query_db)
    pending_matches = query_db("SELECT m.*, li.item_name as lost_name, li.image_urls as lost_images, li.phone as lost_phone, fi.item_name as found_name, fi.image_urls as found_images, fi.phone as found_phone FROM matches m JOIN items li ON m.lost_item_id = li.id JOIN items fi ON m.found_item_id = fi.id WHERE m.status='pending' ORDER BY m.created_at DESC")
    
    for pm in pending_matches:
        if pm.get('lost_images'):
            pm['lost_images_list'] = json.loads(pm['lost_images'])
        else:
            pm['lost_images_list'] = []
        if pm.get('found_images'):
            pm['found_images_list'] = json.loads(pm['found_images'])
        else:
            pm['found_images_list'] = []
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal - Admin</span>
  <span style="display:flex;align-items:center;">
    <a href="{{ url_for('admin_dashboard') }}" class="btn">← Back to Dashboard</a>
  </span>
</div>
<div class='main'>
  <h2>Match Items</h2>
  <div class="pending-matches">
    <h3>Pending Matches ({{ pending_matches|length }}) - Sorted by Date</h3>
    {% for pm in pending_matches %}
    <div class="match-card">
      <h4>Lost: {{ pm['lost_name'] }} | Found: {{ pm['found_name'] }}</h4>
      {% if pm['lost_phone'] %}
      <small>Lost Phone: {{ pm['lost_phone'] }}</small>
      {% endif %}
      {% if pm['found_phone'] %}
      <small>Found Phone: {{ pm['found_phone'] }}</small>
      {% endif %}
      <div class="match-images">
        <div>
          <span class="match-label">Lost Images:</span>
          {% if pm['lost_images_list'] %}
            <div class="images-row">
              {% for url in pm['lost_images_list'][:3] %}
              <img src="{{ url }}" alt="Lost Image" class="thumbnail">
              {% endfor %}
            </div>
          {% endif %}
        </div>
        <div>
          <span class="match-label">Found Images:</span>
          {% if pm['found_images_list'] %}
            <div class="images-row">
              {% for url in pm['found_images_list'][:3] %}
              <img src="{{ url }}" alt="Found Image" class="thumbnail">
              {% endfor %}
            </div>
          {% endif %}
        </div>
      </div>
      <div class="match-actions">
        <a href="{{ url_for('admin_approve_match', match_id=pm['id']) }}" class="btn approve">Approve & Notify Both Parties</a>
        <a href="{{ url_for('admin_reject_match', match_id=pm['id']) }}" class="btn reject">Reject</a>
      </div>
    </div>
    {% endfor %}
  </div>
  <h3>Potential Matches (Fuzzy, Sorted by Score)</h3>
  <div class="card-grid">
    {% for match in potential_matches %}
    <div class="card match">
      <span class="type">Potential (Score: {{ "%.2f"|format(match['score']) }})</span>
      <h4>Lost: {{ match['lost']['item_name'] }}</h4>
      <p>{{ match['lost']['description'] }}</p>
      {% if match['lost']['phone'] %}
      <small>Phone: {{ match['lost']['phone'] }}</small>
      {% endif %}
      {% if match['lost']['image_urls_list'] %}
        <div class="images-row">
          {% for url in match['lost']['image_urls_list'][:3] %}
          <img src="{{ url }}" alt="Lost Image" class="thumbnail">
          {% endfor %}
        </div>
      {% endif %}
      <h4>Found: {{ match['found']['item_name'] }}</h4>
      <p>{{ match['found']['description'] }}</p>
      {% if match['found']['phone'] %}
      <small>Phone: {{ match['found']['phone'] }}</small>
      {% endif %}
      {% if match['found']['image_urls_list'] %}
        <div class="images-row">
          {% for url in match['found']['image_urls_list'][:3] %}
          <img src="{{ url }}" alt="Found Image" class="thumbnail">
          {% endfor %}
        </div>
      {% endif %}
      <form method="POST" action="{{ url_for('admin_create_match') }}" style="margin-top:10px;">
        <input type="hidden" name="lost_id" value="{{ match['lost']['id'] }}">
        <input type="hidden" name="found_id" value="{{ match['found']['id'] }}">
        <button type="submit" class="btn approve">Create Pending Match</button>
      </form>
    </div>
    {% endfor %}
  </div>
  {% if not potential_matches %}
  <p style="text-align:center; color:#666;">No potential matches. Return some found items first.</p>
  {% endif %}
</div>
<div class='footer'>© 2025 Lost & Found Portal (Admin)</div>
</div>
""", potential_matches=potential_matches, pending_matches=pending_matches)


@app.route("/admin_create_match", methods=["POST"])
def admin_create_match():
    """Create a new pending match"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    lost_id = request.form.get("lost_id")
    found_id = request.form.get("found_id")
    
    if not lost_id or not found_id:
        flash("Invalid match data.")
        return redirect(url_for("admin_matches"))
    
    try:
        lost_id = int(lost_id)
        found_id = int(found_id)
    except ValueError:
        flash("Invalid IDs provided.")
        return redirect(url_for("admin_matches"))
    
    if lost_id == 0 or found_id == 0:
        flash("Invalid match IDs.")
        return redirect(url_for("admin_matches"))
    
    lost = query_db("SELECT * FROM items WHERE id=%s", (lost_id,), fetchone=True)
    found = query_db("SELECT * FROM items WHERE id=%s", (found_id,), fetchone=True)
    
    if lost and found:
        query_db("""
            INSERT INTO matches (lost_item_id, found_item_id, lost_email, found_email)
            VALUES (%s, %s, %s, %s)
        """, (lost['id'], found['id'], lost['user_email'], found['user_email']), commit=True)
        
        admin_msg = f"New match created: Lost ID {lost['id']} ({lost['item_name']}) matched with Found ID {found['id']} ({found['item_name']}). Please review and notify parties."
        query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", ('admin', admin_msg), commit=True)
    else:
        flash("Lost or found item not found.")
    
    return redirect(url_for("admin_matches"))


@app.route("/admin_approve_match/<int:match_id>")
def admin_approve_match(match_id):
    """Approve a match and notify both parties"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    m = query_db("SELECT * FROM matches WHERE id=%s", (match_id,), fetchone=True)
    if m:
        lost_item = query_db("SELECT * FROM items WHERE id=%s", (m['lost_item_id'],), fetchone=True)
        found_item = query_db("SELECT * FROM items WHERE id=%s", (m['found_item_id'],), fetchone=True)
        
        if lost_item and found_item:
            query_db("UPDATE items SET status='matched' WHERE id=%s OR id=%s", (m['lost_item_id'], m['found_item_id']), commit=True)
            query_db("UPDATE matches SET status='approved' WHERE id=%s", (match_id,), commit=True)
            
            loser_email = m['lost_email']
            finder_email = m['found_email']
            finder_phone = found_item.get('phone', 'N/A')
            loser_phone = lost_item.get('phone', 'N/A')
            
            loser_subject = "Lost Item Found!"
            loser_body = f"""Hi,
'{lost_item['item_name']}' matched & at AIML office.
Desc: {lost_item['description'][:100]}
Found: {found_item['description'][:100]}
Loc: {found_item['location']}
Finder Phone: {finder_phone}
Collect soon.
AIML Lost & Found."""
            
            finder_subject = "Found Item Matched!"
            finder_body = f"""Hi,
'{found_item['item_name']}' matched with lost item.
Lost: {lost_item['description'][:100]}
Owner Phone: {loser_phone}
Owner notified. Thanks!
AIML Lost & Found."""
            
            ok_loser, info_loser = send_email(loser_email, loser_subject, loser_body, mail)
            ok_finder, info_finder = send_email(finder_email, finder_subject, finder_body, mail)
            
            note_loser = f"Match approved and email sent to loser: {info_loser}" if ok_loser else f"Match approved but email to loser failed: {info_loser}"
            note_finder = f"Email sent to finder: {info_finder}" if ok_finder else f"Email to finder failed: {info_finder}"
            
            query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", (loser_email, note_loser), commit=True)
            query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", (finder_email, note_finder), commit=True)
            query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", ('admin', f"Match {match_id} approved. Emails sent to both parties."), commit=True)
        else:
            flash("Items not found.")
    
    return redirect(url_for("admin_matches"))


@app.route("/admin_reject_match/<int:match_id>")
def admin_reject_match(match_id):
    """Reject a match"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    m = query_db("SELECT * FROM matches WHERE id=%s", (match_id,), fetchone=True)
    if m:
        query_db("UPDATE matches SET status='rejected' WHERE id=%s", (match_id,), commit=True)
        query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)",
                 (m['lost_email'], f"Match rejected by admin for lost item ID {m['lost_item_id']}"), commit=True)
        query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)",
                 (m['found_email'], f"Match rejected by admin for found item ID {m['found_item_id']}"), commit=True)
        query_db("INSERT INTO notifications (user_email, message) VALUES (%s, %s)", ('admin', f"Match {match_id} rejected."), commit=True)
        flash("Match rejected. Notifications sent to parties.")
    
    return redirect(url_for("admin_matches"))


@app.route("/admin_mark_collected/<int:item_id>")
def admin_mark_collected(item_id):
    """Mark item as collected"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    query_db("UPDATE items SET status='collected' WHERE id=%s", (item_id,), commit=True)
    query_db("UPDATE matches SET status='collected' WHERE found_item_id=%s", (item_id,), commit=True)
    flash("Item marked as collected.")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin_delete/<int:item_id>")
def admin_delete(item_id):
    """Delete an item and related matches"""
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
    
    query_db("DELETE FROM matches WHERE lost_item_id = %s OR found_item_id = %s", (item_id, item_id), commit=True)
    query_db("DELETE FROM items WHERE id=%s", (item_id,), commit=True)
    flash("Item and related matches deleted by admin.")
    
    return redirect(url_for("admin_full_view"))


@app.route("/admin_logout")
def admin_logout():
    """Logout admin"""
    session.pop("admin", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


# ============================================================================
# USER ROUTES
# ============================================================================

@app.route("/")
def root():
    """Root path redirects to welcome"""
    return redirect(url_for("welcome"))


@app.route("/welcome")
def welcome():
    """Welcome page"""
    if "email" in session:
        return redirect(url_for("dashboard"))
    
    return render_template_string(get_base_style("home") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
  <span>
    <a href="{{ url_for('login') }}" class="btn">Login</a>
    <a href="{{ url_for('register') }}" class="btn">Register</a>
    <a href="{{ url_for('admin_login') }}" class="btn">Admin Login</a>
  </span>
</div>
<div class='main'>
  <h1 style="color:#6a11cb;">Welcome to Lost & Found Portal!</h1>
  <p style="text-align:center; font-size:1.1rem; margin:20px 0;">Track and report lost or found items easily within AIML Department.</p>
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    if request.method == "POST":
        email = request.form.get("email")
        fn = request.form.get("first_name")
        ln = request.form.get("last_name")
        pw = request.form.get("password")
        
        if not all([email, fn, ln, pw]):
            flash("All fields required.")
            return redirect(url_for("register"))
        
        if len(pw) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))
        
        pw = generate_password_hash(pw)
        try:
            query_db("INSERT INTO users (email, first_name, last_name, password) VALUES (%s, %s, %s, %s)", (email, fn, ln, pw), commit=True)
            flash("Registered successfully!")
            return redirect(url_for("login"))
        except:
            flash("Email already registered.")
    
    return render_template_string(get_base_style("auth") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
</div>
<div class='main' style='max-width:540px;margin-top:40px;'>
<h2>Register</h2>
<form method="POST" autocomplete="off">
<input name="email" type="email" placeholder="Email" required autocomplete="off"><br>
<input name="first_name" placeholder="First Name" required autocomplete="off"><br>
<input name="last_name" placeholder="Last Name" required autocomplete="off"><br>
<input name="password" type="password" placeholder="Password" required autocomplete="new-password"><br>
<button type="submit" class="btn">Register</button>
</form>
<p>Already have an account? <a href="{{ url_for('login') }}">Login</a></p>
{% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login"""
    if request.method == "POST":
        email = request.form.get("email")
        pw = request.form.get("password")
        
        if not email or not pw:
            flash("Email and password required.")
            return redirect(url_for("login"))
        
        row = query_db("SELECT * FROM users WHERE email=%s", (email,), fetchone=True)
        if row and check_password_hash(row["password"], pw):
            session.clear()
            session["email"] = email
            session["first_name"] = row["first_name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials.")
    
    return render_template_string(get_base_style("auth") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
</div>
<div class='main' style='max-width:440px;margin-top:40px;'>
<h2>Login</h2>
<form method="POST" autocomplete="off">
<input name="email" type="email" placeholder="Email" required autocomplete="off"><br>
<input name="password" type="password" placeholder="Password" required autocomplete="new-password"><br>
<button type="submit" class="btn">Login</button>
</form>
<p>Don't have an account? <a href="{{ url_for('register') }}">Register</a></p>
{% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""")


@app.route("/dashboard")
def dashboard():
    """User dashboard"""
    if "email" not in session:
        return redirect(url_for("login"))
    
    items = query_db("SELECT * FROM items ORDER BY id DESC")
    
    for item in items:
        if item.get('image_urls'):
            item['image_urls_list'] = json.loads(item['image_urls'])
        else:
            item['image_urls_list'] = []
    
    user_lost = [i for i in items if i['type'] == 'Lost' and i['user_email'] == session["email"]]
    user_found = [i for i in items if i['type'] == 'Found' and i['user_email'] == session["email"]]
    lost_count = len(user_lost)
    found_count = len(user_found)
    
    user_matches = []
    for item in user_lost:
        matches = query_db("SELECT * FROM matches WHERE lost_item_id=%s ORDER BY created_at DESC", (item['id'],))
        user_matches.extend(matches)
    for item in user_found:
        matches = query_db("SELECT * FROM matches WHERE found_item_id=%s ORDER BY created_at DESC", (item['id'],))
        user_matches.extend(matches)
    
    user_matches.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    for m in user_matches:
        lost_img_row = query_db("SELECT image_urls FROM items WHERE id=%s", (m['lost_item_id'],), fetchone=True)
        m['lost_image_urls_list'] = json.loads(lost_img_row['image_urls']) if lost_img_row and lost_img_row['image_urls'] else []
        found_img_row = query_db("SELECT image_urls FROM items WHERE id=%s", (m['found_item_id'],), fetchone=True)
        m['found_image_urls_list'] = json.loads(found_img_row['image_urls']) if found_img_row and found_img_row['image_urls'] else []
    
    user_notifications = len(user_matches)
    user_item_ids = {i['id'] for i in user_lost + user_found}
    all_matches = query_db("SELECT lost_item_id, found_item_id FROM matches")
    lost_matches_count = {mid: 0 for mid in user_item_ids}
    found_matches_count = {mid: 0 for mid in user_item_ids}
    
    for m in all_matches:
        if m['lost_item_id'] in user_item_ids:
            lost_matches_count[m['lost_item_id']] += 1
        if m['found_item_id'] in user_item_ids:
            found_matches_count[m['found_item_id']] += 1
    
    for item in items:
        if item['id'] in user_item_ids:
            if item['type'] == 'Lost':
                item['match_count'] = lost_matches_count.get(item['id'], 0)
                item['matches'] = query_db("SELECT m.status, fi.item_name as found_name, fi.phone as found_phone FROM matches m JOIN items fi ON m.found_item_id = fi.id WHERE m.lost_item_id = %s AND m.status IN ('approved', 'collected') ORDER BY m.created_at DESC LIMIT 1", (item['id'],), fetchone=True) or {}
            else:
                item['match_count'] = found_matches_count.get(item['id'], 0)
                item['matches'] = query_db("SELECT m.status, li.item_name as lost_name, li.phone as lost_phone FROM matches m JOIN items li ON m.lost_item_id = li.id WHERE m.found_item_id = %s AND m.status IN ('approved', 'collected') ORDER BY m.created_at DESC LIMIT 1", (item['id'],), fetchone=True) or {}
        else:
            item['match_count'] = 0
            item['matches'] = {}
    
    return render_template_string(get_base_style("dashboard") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
  <span style="display:flex;align-items:center;">
    <a href="#matches" class="notif" title="View Matches" style="text-decoration:none;">
      🔔
      {% if user_notifications > 0 %}
      <span class="badge">{{ user_notifications }}</span>
      {% endif %}
    </a>
    <span class='user'>Hi, {{ session['first_name'] }} | <a href="{{ url_for('logout') }}" class="btn">Logout</a></span>
  </span>
</div>
<div class='main'>
  <div class="dashboard-header" style="margin-bottom:32px;">
    <h2 style="margin-bottom:0;">Dashboard</h2>
    <span class="college">AIML Department</span>
  </div>
  <div class="card-stats" style="margin-bottom:36px;">
    <div class="stat-card lost">
      <span class="icon">🛑</span>
      <h3>Your Lost</h3>
      <div class="count">{{ lost_count }}</div>
    </div>
    <div class="stat-card found">
      <span class="icon">🔍</span>
      <h3>Your Found</h3>
      <div class="count">{{ found_count }}</div>
    </div>
    <div class="stat-card match">
      <span class="icon">🤝</span>
      <h3>Your Matches</h3>
      <div class="count">{{ user_notifications }}</div>
    </div>
  </div>
  <div style="display:flex; justify-content:center; gap:24px; margin-bottom:32px; flex-wrap:wrap;">
    <a href="{{ url_for('upload', type_='Lost') }}" class="btn" style="background:linear-gradient(90deg,#ff8a65,#ff5252);color:#fff;font-size:1.1rem;box-shadow:0 4px 12px rgba(255,82,82,0.2);">
      <span style="font-size:1.3rem;vertical-align:middle;">➕</span> Report Lost
    </a>
    <a href="{{ url_for('upload', type_='Found') }}" class="btn" style="background:linear-gradient(90deg,#4caf50,#45a049);color:#fff;font-size:1.1rem;box-shadow:0 4px 12px rgba(76,175,80,0.2);">
      <span style="font-size:1.3rem;vertical-align:middle;">🔍</span> Report Found
    </a>
  </div>
  <h3 style="color:#6a11cb; margin-bottom:20px;">All Items</h3>
  <div class="card-grid">
    {% for item in items %}
    <div class="card {% if item['type'] == 'Lost' and item['status'] == 'pending' %}lost pending{% elif item['type'] == 'Lost' %}lost{% elif item['status'] == 'returned' or item['status'] == 'matched' %}found returned{% else %}found{% endif %}">
      <span class="type">{{ item['type'] }} - {{ item['status'] }}</span>
      <div class="edit-delete">
        {% if item['status'] == 'pending' and item['user_email'] == session['email'] %}
          <a href="{{ url_for('edit_item', item_id=item['id']) }}" title="Edit">✏️</a>
        {% endif %}
      </div>
      <strong style="font-size:1.2rem;display:block;margin-bottom:8px;">{{ item['item_name'] }}</strong>
      <p style="margin-bottom:12px;word-break:break-word;line-height:1.4;">{{ item['description'] }}</p>
      <small style="color:#666;">Location: <b>{{ item['location'] }}</b></small>
      <small style="color:#666; display:block; margin-top:4px;">User: <b>{{ item['user_email'] }}</b></small>
      {% if item['match_count'] > 0 and item['matches'] %}
      <div class="match-preview">
        <h5>Match: {{ item['matches']['status'].title() }}</h5>
        <small>{% if item['type'] == 'Lost' %}{{ item['matches']['found_name'] }} (Phone: {{ item['matches']['found_phone'] or 'N/A' }}){% else %}{{ item['matches']['lost_name'] }} (Phone: {{ item['matches']['lost_phone'] or 'N/A' }}){% endif %}</small>
      </div>
      {% elif item['match_count'] > 0 %}
      <small style="color:#388e3c; font-weight:600; display:block; margin-top:4px;">Matches: {{ item['match_count'] }} <span style="background:#e8f5e9; padding:2px 6px; border-radius:4px; font-size:0.8rem;">🤝</span></small>
      {% endif %}
      {% if item['type'] == 'Found' and item['phone'] %}
      <small style="color:#666; display:block; margin-top:4px;">Phone: <b>{{ item['phone'] }}</b></small>
      {% endif %}
      {% if item['image_urls_list'] %}
        <div class="images-row">
          {% for url in item['image_urls_list'] %}
          <img src="{{ url }}" alt="Item Image" class="thumbnail">
          {% endfor %}
        </div>
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% if not items %}
  <p style="text-align:center; color:#666; padding:40px;">No items reported yet. Start by reporting a lost or found item!</p>
  {% endif %}
  <h3 id="matches" style="color:#6a11cb; margin-top:40px;margin-bottom:20px;">Your Matches (Sorted by Date)</h3>
  <div class="card-grid">
    {% for m in user_matches %}
    <div class="card match {% if m['status'] == 'approved' or m['status'] == 'collected' %}matched{% else %}pending{% endif %}">
      <span class="type">Match Status: {{ m['status'] }}</span>
      <h4 style="color:#388e3c;margin-bottom:8px;">{% if m['lost_email'] == session['email'] %}Your Lost Item Matched!{% else %}Your Found Item Matched!{% endif %}</h4>
      <p style="margin-bottom:12px;">Status: {{ m['status'] }}. Please check with admin if approved for collection.</p>
      <div class="match-images">
        {% if m['lost_image_urls_list'] %}
          <div>
            <span class="match-label">Lost Images:</span>
            <div class="images-row">
              {% for url in m['lost_image_urls_list'][:3] %}
              <img src="{{ url }}" alt="Lost Image" class="thumbnail">
              {% endfor %}
            </div>
          </div>
        {% endif %}
        {% if m['found_image_urls_list'] %}
          <div>
            <span class="match-label">Found Images:</span>
            <div class="images-row">
              {% for url in m['found_image_urls_list'][:3] %}
              <img src="{{ url }}" alt="Found Image" class="thumbnail">
              {% endfor %}
            </div>
          </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
  {% if not user_matches %}
  <p style="text-align:center;color:#666;padding:20px;">No matches yet. Admin will notify you when one is found.</p>
  {% endif %}
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""", items=items, lost_count=lost_count, found_count=found_count, user_matches=user_matches, user_notifications=user_notifications)


@app.route("/logout")
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for("welcome"))


@app.route("/upload/<type_>", methods=["GET", "POST"])
def upload(type_):
    """Report lost or found item"""
    type_item = type_
    
    if "email" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        name = request.form.get("item_name")
        desc = request.form.get("description")
        loc = request.form.get("location")
        phone = request.form.get("phone", "") if type_item == "Found" else None
        
        if not all([name, desc, loc]):
            flash("Name, description, and location required.")
            return redirect(url_for("upload", type_=type_item))
        
        if len(desc) < 10:
            flash("Description too short (min 10 chars).")
            return redirect(url_for("upload", type_=type_item))
        
        files = request.files.getlist("images")
        image_urls = []
        
        for file in files:
            if file and file.filename and file.content_type.startswith('image/'):
                try:
                    res = cloudinary.uploader.upload(file)
                    image_url = res.get("secure_url") or res.get("url")
                    if image_url:
                        image_urls.append(image_url)
                except Exception as e:
                    app.logger.warning(f"Upload failed for {file.filename}: {e}")
        
        image_urls_json = json.dumps(image_urls) if image_urls else None
        
        base_columns = "user_email, type, item_name, description, location, image_urls, status"
        base_values = "(%s, %s, %s, %s, %s, %s, %s)"
        base_args = (session["email"], type_item, name, desc, loc, image_urls_json, 'pending')
        
        if type_item == "Found" and phone:
            if not phone.replace('-', '').replace(' ', '').isdigit() or len(phone.replace('-', '').replace(' ', '')) < 10:
                flash("Invalid phone number.")
                return redirect(url_for("upload", type_=type_item))
            base_columns += ", `phone`"
            base_values = "(%s, %s, %s, %s, %s, %s, %s, %s)"
            base_args = base_args + (phone,)
        
        query_str = f"INSERT INTO items ({base_columns}) VALUES {base_values}"
        item_id = query_db(query_str, base_args, commit=True, return_id=True)
        
        if type_item == "Found":
            subject = "Found Item Reported"
            body = f"""Hi {session['first_name']},
{name} reported. Return to AIML office.
Desc: {desc[:100]}
Loc: {loc}
Phone: {phone or 'N/A'}
Admin review pending.
AIML Lost & Found."""
            send_email(session["email"], subject, body, mail)
            flash("Found item reported! Check your email for return instructions. Admin approval pending.")
        else:
            flash(f"{type_item} item reported! Admin will handle matching.")
        
        return redirect(url_for("dashboard"))
    
    return render_template_string(get_base_style("view") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
  <span class='user'>Hi, {{ session['first_name'] }}</span>
</div>
<div class='main' style='max-width:600px; padding:16px;'>
<h2 style='margin-bottom:8px;'>Report {{ type_item }} Item</h2>
<form method="POST" enctype="multipart/form-data" class="form-compact">
  <input name="item_name" placeholder="Item Name" required>
  <textarea name="description" placeholder="Description (details help matching)" required></textarea>
  <input name="location" placeholder="Location" required>
  {% if type_item == 'Found' %}
  <input name="phone" placeholder="Your Phone Number (optional for contact)" type="tel">
  {% endif %}
  <input type="file" name="images" accept="image/*" multiple>
  <button type="submit" class="btn" style='margin-top:4px;'>Submit</button>
</form>
<a href="{{ url_for('dashboard') }}" class="btn" style='margin-top:8px; display:block;'>Back to Dashboard</a>
{% with messages = get_flashed_messages() %}{% if messages %}<ul style='margin:8px 0; padding-left:20px; color:#4caf50;'>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""", type_item=type_item)


@app.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    """Edit pending item"""
    if "email" not in session:
        return redirect(url_for("login"))
    
    item = query_db("SELECT * FROM items WHERE id=%s AND user_email=%s", (item_id, session["email"]), fetchone=True)
    
    if not item:
        flash("Item not found or unauthorized.")
        return redirect(url_for("dashboard"))
    
    if item["status"] != "pending":
        flash("Cannot edit non-pending items.")
        return redirect(url_for("dashboard"))
    
    if item.get('image_urls'):
        item['image_urls_list'] = json.loads(item['image_urls'])
    else:
        item['image_urls_list'] = []
    
    existing_urls = item['image_urls_list']
    
    if request.method == "POST":
        name = request.form.get("item_name")
        desc = request.form.get("description")
        loc = request.form.get("location")
        phone = request.form.get("phone", item.get('phone', '')) if item['type'] == 'Found' else None
        
        if not all([name, desc, loc]):
            flash("Name, description, and location required.")
            return redirect(url_for("edit_item", item_id=item_id))
        
        files = request.files.getlist("images")
        new_image_urls = []
        
        for file in files:
            if file and file.filename and file.content_type.startswith('image/'):
                try:
                    res = cloudinary.uploader.upload(file)
                    new_image_url = res.get("secure_url") or res.get("url")
                    if new_image_url:
                        new_image_urls.append(new_image_url)
                except Exception as e:
                    app.logger.warning(f"Upload failed: {e}")
        
        updated_urls = existing_urls + new_image_urls
        image_urls_json = json.dumps(updated_urls) if updated_urls else None
        
        update_args = (name, desc, loc, image_urls_json, item_id)
        update_str = "UPDATE items SET item_name=%s, description=%s, location=%s, image_urls=%s WHERE id=%s"
        
        if item['type'] == 'Found' and phone:
            if phone and not phone.replace('-', '').replace(' ', '').isdigit() or len(phone.replace('-', '').replace(' ', '')) < 10:
                flash("Invalid phone number.")
                return redirect(url_for("edit_item", item_id=item_id))
            update_args = (name, desc, loc, image_urls_json, phone, item_id)
            update_str = "UPDATE items SET item_name=%s, description=%s, location=%s, image_urls=%s, phone=%s WHERE id=%s"
        
        query_db(update_str, update_args, commit=True)
        flash("Item updated successfully!")
        return redirect(url_for("dashboard"))
    
    return render_template_string(get_base_style("view") + """
<div class="container">
<div class='navbar'>
  <span class='logo'>Lost & Found Portal</span>
  <span class='user'>Hi, {{ session['first_name'] }}</span>
</div>
<div class='main' style='max-width:720px;'>
<h2>Edit {{ item['type'] }} Item</h2>
<form method="POST" enctype="multipart/form-data">
<input name="item_name" placeholder="Item Name" value="{{ item['item_name'] }}" required><br>
<textarea name="description" placeholder="Description" required rows="4">{{ item['description'] }}</textarea><br>
<input name="location" placeholder="Location" value="{{ item['location'] }}" required><br>
{% if item['type'] == 'Found' %}
<input name="phone" placeholder="Phone Number" value="{{ item['phone'] or '' }}" type="tel"><br>
{% endif %}
<input type="file" name="images" accept="image/*" multiple><br>
{% if item['image_urls_list'] %}
  <div class="images-row">
    {% for url in item['image_urls_list'] %}
    <img src="{{ url }}" alt="Current Image" class="thumbnail">
    {% endfor %}
  </div>
  <p style="font-size:0.9em; color:#666;">Current images shown above. New uploads will be added.</p>
{% endif %}
<button type="submit" class="btn">Update Item</button>
</form>
<a href="{{ url_for('dashboard') }}" class="btn">Back to Dashboard</a>
{% with messages = get_flashed_messages() %}{% if messages %}<ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>{% endif %}{% endwith %}
</div>
<div class='footer'>© 2025 Lost & Found Portal</div>
</div>
""", item=item)


@app.route("/test_mail")
def test_mail():
    """Test email functionality"""
    target = session.get("email") or app.config.get("MAIL_USERNAME")
    if not target:
        return "No target email set."
    ok, info = send_email(target, "Test Email", "This is a test email from the Lost & Found app.", mail)
    return f"Email {'sent successfully!' if ok else f'failed: {info}'}"


if __name__ == "__main__":
    app.run(debug=True)
