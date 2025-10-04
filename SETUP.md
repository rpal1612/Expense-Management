# ExpenseFlow Setup Guide

## Prerequisites
1. PostgreSQL installed and running
2. Python 3.7+ installed
3. Git (optional)

## Setup Steps

### 1. Database Setup
1. Install and start PostgreSQL
2. Open pgAdmin or use PostgreSQL command line
3. Create a new database named `ExpenseFlow`:
   ```sql
   CREATE DATABASE "ExpenseFlow";
   ```
4. Connect to the ExpenseFlow database
5. Run the SQL script from `db.sql` to create tables and initial data:
   - In pgAdmin: Open Query Tool and paste the contents of `db.sql`
   - Or use command line: `psql -U postgres -d ExpenseFlow -f db.sql`

### 2. Python Environment Setup
```bash
# Install required packages
pip install -r requirements.txt
```

### 3. Configure Environment
The `.env` file contains database configuration. Update if needed:
```
DB_USER=postgres
DB_PASSWORD=root
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ExpenseFlow
```

### 4. Setup Database with Test Users
```bash
python setup_db.py
```

This will create test users with the following credentials:
- **Admin**: john.admin@flow.com / admin123
- **Manager**: sarah.manager@flow.com / manager123  
- **Employee**: mike.employee@flow.com / employee123
- **Employee**: emily.employee@flow.com / employee123

### 5. Start the Application
```bash
python app.py
```

The application will be available at: http://localhost:3000

## Testing the System

### Signup Test
1. Go to http://localhost:3000
2. Click "Register" 
3. Fill in the signup form with new user details
4. Submit the form
5. Check pgAdmin to verify the user was created in the database

### Login Test
1. Use the login form with either:
   - Test credentials from setup_db.py
   - New credentials you created via signup
2. Select the appropriate role
3. You should be redirected to the relevant dashboard

## Database Tables Created
- `Companies` - Company information
- `Users` - User accounts with hashed passwords
- `Expenses` - Expense submissions
- `ApprovalWorkflows` & `WorkflowSteps` - Approval process configuration
- `ConditionalRules` - Business rules for approvals
- `ApprovalTransactions` - Approval history

## Features Implemented
- ✅ User Registration (Signup)
- ✅ User Authentication (Login)
- ✅ Password hashing with Werkzeug
- ✅ PostgreSQL database integration
- ✅ Role-based access (Admin, Manager, Employee)
- ✅ CORS enabled for frontend-backend communication
- ✅ Form validation (client-side and server-side)
- ✅ Loading states and error handling
- ✅ Responsive UI design

## API Endpoints
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/health` - System health check
- `GET /` - Serve main page
- `GET /admin/dashboard` - Admin dashboard
- `GET /manager/dashboard` - Manager dashboard  
- `GET /employee/dashboard` - Employee dashboard

## Troubleshooting

### Database Connection Issues
1. Ensure PostgreSQL is running
2. Check database credentials in `.env`
3. Verify database `ExpenseFlow` exists
4. Run `python setup_db.py` to test connection

### Import Errors
1. Make sure all packages are installed: `pip install -r requirements.txt`
2. Use a virtual environment if needed

### CORS Issues
1. Flask-CORS is configured to allow all origins in development
2. For production, configure specific allowed origins

### Port Issues
1. If port 3000 is busy, change the port in `app.py`
2. Update any hardcoded URLs in JavaScript if needed
