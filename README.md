# Expense-Management
Team Members :
Sanika Jade - leader,
Riya Pal ,
Sanjana Kurade

### Problem Statement - Expense Management
### Reviewer -  Aman Patel 
### video link :- https://drive.google.com/drive/folders/1BYzaXg1C4uHNtBlKa6RHlXjwZMoLTJpB?usp=sharing

## ExpenseFlow
A lightweight Flask-based expense management system with multi-level approval workflows, admin override capabilities, OCR receipt parsing, and a responsive admin/manager UI.
## Key Features
- Submit and store expense claims with OCR-assisted receipt parsing
- Multi-level approval workflows and conditional rules
- Admin “View All Expenses” with override (approve/reject)
- Manager dashboard for team approvals and statistics
- REST API endpoints for frontend integration
- PostgreSQL persistence; easy seeded test users
## Tech Stack
- Backend: Python, Flask
- Database: PostgreSQL
- Frontend: HTML/CSS/vanilla JS (server-served templates)
- OCR: Tesseract (pytesseract)
- Auth: werkzeug password hashing
## Quickstart (Windows PowerShell)
# Prerequisites : 
- Python 3.8+
- PostgreSQL running and accessible
- Tesseract OCR installed (if using receipt extraction)


1.Install dependencies:
      ``` pip install -r requirements.txt```
               
2.Configure environment

Copy or create a .env in project root with values: 
- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
- (optional) FLASK_ENV, SECRET_KEY Example (.env) DB_HOST=localhost DB_PORT=5432 DB_NAME=expense_management DB_USER=postgres DB_PASSWORD=yourpassword

3.Initialize database

Option A: Run provided SQL seed
- Use psql or PG client to run db.sql

Option B: Use setup script powershell python setup_db.py (Scripts create Users, Expenses, ApprovalWorkflows and seed test data.)

4.Run the app

- Main backend (app.py): ```python app.py```

Default ports are configured in files; check console logs for the port.

5.Open UI
- Admin: http://localhost:3000/admin/dashboard (or port shown by app)
- Manager: http://localhost:3000/manager/dashboard
- Employee: corresponding routes as configured

## UI 

![WhatsApp Image 2025-10-04 at 18 44 48_c37a8fdc](https://github.com/user-attachments/assets/dbe3f164-9545-42e3-a381-341e6ae4a610)

<img width="1816" height="831" alt="image" src="https://github.com/user-attachments/assets/f5f1b244-032a-41dc-8f5c-dc0a63a8f16e" />

<img width="1475" height="769" alt="image" src="https://github.com/user-attachments/assets/9268db7b-2006-4c42-ad09-f5fd710d9621" />

<img width="1800" height="826" alt="image" src="https://github.com/user-attachments/assets/45599cba-32ea-47a3-8c95-6571dcb4154a" />

<img width="1795" height="817" alt="image" src="https://github.com/user-attachments/assets/f132e339-d337-4df0-8915-e9c8b5da5433" />

<img width="1795" height="932" alt="image" src="https://github.com/user-attachments/assets/897c95d0-4dd0-4fcc-8133-87a09a528756" />




## License
This project is licensed under the MIT License - see the LICENSE file for details.
