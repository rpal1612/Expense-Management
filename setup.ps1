# ExpenseFlow Setup Script for Windows
# Run this in PowerShell as Administrator

Write-Host "ExpenseFlow Setup Script" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green

# Check if Python is installed
try {
    $pythonVersion = python --version
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.7+ first." -ForegroundColor Red
    exit 1
}

# Check if PostgreSQL is accessible
Write-Host "`nChecking PostgreSQL..." -ForegroundColor Yellow
try {
    # Try to connect to PostgreSQL (you might need to adjust this)
    Write-Host "Please ensure PostgreSQL is running and ExpenseFlow database exists" -ForegroundColor Yellow
} catch {
    Write-Host "Warning: Could not verify PostgreSQL connection" -ForegroundColor Yellow
}

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
try {
    pip install -r requirements.txt
    Write-Host "✓ Dependencies installed successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Setup database
Write-Host "`nSetting up database..." -ForegroundColor Yellow
try {
    python setup_db.py
    Write-Host "✓ Database setup completed" -ForegroundColor Green
} catch {
    Write-Host "✗ Database setup failed" -ForegroundColor Red
    Write-Host "Please ensure PostgreSQL is running and ExpenseFlow database exists" -ForegroundColor Yellow
}

Write-Host "`n" + "=" * 50 -ForegroundColor Green
Write-Host "Setup completed!" -ForegroundColor Green
Write-Host "`nTo start the application:" -ForegroundColor Yellow
Write-Host "  python app.py" -ForegroundColor Cyan
Write-Host "`nThen visit: http://localhost:3000" -ForegroundColor Cyan
Write-Host "`nTest credentials:" -ForegroundColor Yellow
Write-Host "  Admin: john.admin@flow.com / admin123" -ForegroundColor Cyan
Write-Host "  Manager: sarah.manager@flow.com / manager123" -ForegroundColor Cyan
Write-Host "  Employee: mike.employee@flow.com / employee123" -ForegroundColor Cyan
