# Lost & Found Portal

A Flask-based Lost & Found management system for the AIML Department with admin matching and email notifications.

## Project Structure

```
lost-and-found/
├── app.py              # Flask routes and main application
├── config.py           # Configuration settings
├── db.py               # Database connection and queries
├── utils.py            # Utility functions (email, PDF, fuzzy matching)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
└── templates/          # HTML templates directory (future use)
```

## Features

- **User Management**: Registration, login, and dashboard
- **Item Reporting**: Report lost or found items with images
- **Fuzzy Matching**: Automatic matching of lost and found items
- **Admin Panel**: Approve returns, manage matches, generate reports
- **PDF Reports**: Export statistics and item data to PDF
- **Email Notifications**: Notify users of matches and status updates
- **Cloudinary Integration**: Image upload and management

## Setup Instructions

### 1. Clone or Download the Repository

```bash
cd lost-and-found
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your configuration:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- Database credentials
- Cloudinary credentials
- Email (Gmail) credentials
- Admin password

### 5. Initialize Database

The database tables will be created automatically when the app runs for the first time.

### 6. Run the Application

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

## Configuration Details

### Database (MySQL)
- Default host: `localhost`
- Default user: `flaskuser`
- Default database: `lf_db`

### Cloudinary
- Sign up at https://cloudinary.com
- Get your cloud name, API key, and API secret
- Add to `.env`

### Gmail (Email)
- Enable 2-factor authentication on Gmail
- Generate an app password: https://myaccount.google.com/apppasswords
- Use the app password in `.env` for `MAIL_PASSWORD`

## File Descriptions

### `app.py`
Contains all Flask routes organized into sections:
- Admin routes (login, dashboard, reports, matching)
- User routes (auth, dashboard, item upload, editing)

### `config.py`
Centralized configuration using environment variables:
- Flask settings
- Database credentials
- Cloudinary settings
- Email configuration
- Session and matching thresholds

### `db.py`
Database operations:
- Connection management
- Query execution with retry logic for lock timeouts
- Table initialization
- Default admin user creation

### `utils.py`
Helper functions:
- Fuzzy string matching for item similarity
- Email sending via Flask-Mail
- PDF report generation with ReportLab
- Image URL conversion (.avif to .png)
- CSS styling for different pages

## Admin Account

- **Default Username**: `admin`
- **Default Password**: Check `ADMIN_PASSWORD` in `.env` (default: `admin123`)

## User Workflows

### Report Lost Item
1. Login as user
2. Click "Report Lost"
3. Fill in item details and upload images
4. Admin will match with found items

### Report Found Item
1. Login as user
2. Click "Report Found"
3. Fill in item details, phone number, and upload images
4. Admin approves return
5. Item can be collected from AIML office

### Admin Workflow
1. Login to admin dashboard
2. Review pending returns
3. Check potential matches using fuzzy matching
4. Approve matches and notify parties
5. Generate reports

## Database Schema

- **users**: User accounts
- **items**: Lost and found items
- **admin**: Admin accounts
- **matches**: Matched lost-found pairs
- **notifications**: System notifications

## Security Notes

- Passwords are hashed using werkzeug.security
- Admin login required for sensitive operations
- Environment variables for sensitive data

## Support

For issues or questions, refer to the documentation or check the code comments.

## License

This project is part of the AIML Department Lost & Found System.
