-- ==============================================================================
-- PostgreSQL Script for Expense Management System
-- This script creates tables for Companies, Users, Expenses, Approval Flows,
-- and Conditional Rules, and inserts initial seed data.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. ENUM Types
-- ------------------------------------------------------------------------------
-- Defines the roles a user can hold in the system.
CREATE TYPE user_role AS ENUM ('Admin', 'Manager', 'Employee');
-- Defines the status of a specific expense claim.
CREATE TYPE expense_status AS ENUM ('Draft', 'Pending', 'Approved', 'Rejected');
-- Defines the types of conditional approval rules.
CREATE TYPE rule_type AS ENUM ('Percentage', 'SpecificApprover', 'Threshold', 'Hybrid');
-- Defines the status of an approval step in a flow.
CREATE TYPE approval_step_status AS ENUM ('Waiting', 'Pending', 'Approved', 'Rejected');


-- ------------------------------------------------------------------------------
-- 2. COMPANY Table (Holds Company-level settings)
-- ------------------------------------------------------------------------------
CREATE TABLE Companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    default_currency_code CHAR(3) NOT NULL DEFAULT 'USD', -- ISO 4217 Currency Code (e.g., USD, EUR)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE Companies IS 'Stores information about each company instance, including default currency.';


-- ------------------------------------------------------------------------------
-- 3. USERS Table (Authentication, Roles, and Hierarchy)
-- ------------------------------------------------------------------------------
CREATE TABLE Users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id INTEGER REFERENCES Companies(company_id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL, -- Stored securely (e.g., bcrypt hash)
    role user_role NOT NULL,
    manager_id UUID REFERENCES Users(user_id) ON DELETE SET NULL, -- Defines reporting hierarchy
    is_manager_approver BOOLEAN NOT NULL DEFAULT FALSE, -- PS requirement: if checked, first approval is by manager
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE Users IS 'Stores user data, role, and manager hierarchy.';


-- ------------------------------------------------------------------------------
-- 4. EXPENSES Table (Submitted Expense Claims)
-- ------------------------------------------------------------------------------
CREATE TABLE Expenses (
    expense_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES Users(user_id) ON DELETE CASCADE NOT NULL,
    company_id INTEGER REFERENCES Companies(company_id) ON DELETE CASCADE NOT NULL,
    -- Core expense details
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL, -- e.g., Meals, Transport, Accommodation, Supplies
    expense_date DATE NOT NULL,
    -- Financials in submitted currency
    submitted_amount NUMERIC(15, 2) NOT NULL CHECK (submitted_amount > 0),
    submitted_currency CHAR(3) NOT NULL,
    -- Converted amount in company's default currency
    converted_amount NUMERIC(15, 2) NOT NULL CHECK (converted_amount > 0),
    conversion_rate NUMERIC(10, 6),
    -- Approval status
    status expense_status NOT NULL DEFAULT 'Draft',
    current_approval_step INTEGER DEFAULT 1,
    -- OCR Data fields (as requested in Additional Features)
    ocr_merchant_name VARCHAR(255),
    ocr_receipt_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE Expenses IS 'Main table for all expense submissions.';


-- ------------------------------------------------------------------------------
-- 5. APPROVAL WORKFLOW Configuration (Multi-level sequence)
-- ------------------------------------------------------------------------------
CREATE TABLE ApprovalWorkflows (
    workflow_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES Companies(company_id) ON DELETE CASCADE NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Defines the sequence of steps within a workflow (Manager, Finance, Director, etc.)
CREATE TABLE WorkflowSteps (
    step_id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES ApprovalWorkflows(workflow_id) ON DELETE CASCADE NOT NULL,
    step_sequence INTEGER NOT NULL, -- 1, 2, 3...
    approver_role user_role, -- Defines who approves this step (e.g., Manager, Admin)
    approver_specific_id UUID REFERENCES Users(user_id) ON DELETE SET NULL, -- Optional: Specific user ID if not role-based (e.g., CFO)
    UNIQUE (workflow_id, step_sequence)
);


-- ------------------------------------------------------------------------------
-- 6. APPROVAL TRANSACTIONS (Log of actual approvals/rejections)
-- ------------------------------------------------------------------------------
CREATE TABLE ApprovalTransactions (
    transaction_id SERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES Expenses(expense_id) ON DELETE CASCADE NOT NULL,
    approver_id UUID REFERENCES Users(user_id) ON DELETE SET NULL,
    step_sequence INTEGER NOT NULL, -- Which step in the overall process this relates to
    status approval_step_status NOT NULL,
    comments TEXT,
    action_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (expense_id, step_sequence)
);

COMMENT ON TABLE ApprovalTransactions IS 'Logs every approval/rejection action for an expense.';


-- ------------------------------------------------------------------------------
-- 7. CONDITIONAL APPROVAL RULES
-- ------------------------------------------------------------------------------
CREATE TABLE ConditionalRules (
    rule_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES Companies(company_id) ON DELETE CASCADE NOT NULL,
    name VARCHAR(255) NOT NULL,
    rule_type rule_type NOT NULL,
    description TEXT,
    -- Rule parameters
    threshold_amount NUMERIC(15, 2), -- Used for 'Threshold' rule type
    percentage_required INTEGER CHECK (percentage_required BETWEEN 1 AND 100), -- Used for 'Percentage' rule type
    specific_approver_role user_role, -- Used for 'SpecificApprover' rule type (e.g., 'Admin' for CFO override)
    target_workflow_step INTEGER, -- Optional: which step this rule applies to or triggers
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE ConditionalRules IS 'Stores flexible rules like Threshold, Percentage, or Specific Approver logic.';


-- ------------------------------------------------------------------------------
-- 8. SEED DATA INSERTION (FIXED CTE ISSUE)
-- ------------------------------------------------------------------------------

-- 8.1. Insert Company
INSERT INTO Companies (name, default_currency_code) VALUES
('ExpenseFlow Corp', 'USD');


-- 8.2. Insert Users (Admin, Manager, Employee)
-- Note: Replace with actual secure hashes in production
INSERT INTO Users (company_id, full_name, email, password_hash, role, is_manager_approver) VALUES
(1, 'John Doe', 'john.admin@flow.com', 'hashed_admin_password', 'Admin', TRUE),
(1, 'Sarah Johnson', 'sarah.manager@flow.com', 'hashed_manager_password', 'Manager', TRUE),
(1, 'Mike Chen', 'mike.employee@flow.com', 'hashed_employee_password', 'Employee', FALSE),
(1, 'Emily Davis', 'emily.employee@flow.com', 'hashed_employee_password_2', 'Employee', FALSE);


-- 8.3. Update Manager Relationships
-- Retrieve IDs using subqueries from the Users table, now that all users exist.
UPDATE Users
SET manager_id = (SELECT user_id FROM Users WHERE full_name = 'John Doe' AND role = 'Admin')
WHERE full_name = 'Sarah Johnson';

UPDATE Users
SET manager_id = (SELECT user_id FROM Users WHERE full_name = 'Sarah Johnson' AND role = 'Manager')
WHERE full_name IN ('Mike Chen', 'Emily Davis');


-- 8.4. Insert Expenses (Aligned with UI mockups)
INSERT INTO Expenses (user_id, company_id, description, category, expense_date, submitted_amount, submitted_currency, converted_amount, conversion_rate, status, current_approval_step, ocr_merchant_name) VALUES
-- Mike Chen's Pending Expense
((SELECT user_id FROM Users WHERE full_name = 'Mike Chen'), 1, 'Client Dinner at Sample Restaurant', 'Meals & Entertainment', '2025-10-03', 285.50, 'USD', 285.50, 1.00, 'Pending', 1, 'Sample Restaurant'),
-- Emily Davis's Approved Expense
((SELECT user_id FROM Users WHERE full_name = 'Emily Davis'), 1, 'Flight to NYC for Q4 Planning', 'Transport', '2025-10-02', 1250.00, 'USD', 1250.00, 1.00, 'Approved', 2, NULL),
-- Mike Chen's Rejected Expense
((SELECT user_id FROM Users WHERE full_name = 'Mike Chen'), 1, 'Taxi Service for personal use', 'Transport', '2025-09-28', 45.00, 'EUR', 48.60, 1.08, 'Rejected', 1, 'City Taxi');


-- 8.5. Insert Approval Workflow Steps (Manager -> Finance -> Director example)
INSERT INTO ApprovalWorkflows (company_id, name) VALUES (1, 'Standard Expense Flow');

INSERT INTO WorkflowSteps (workflow_id, step_sequence, approver_role) VALUES
(1, 1, 'Manager'),    -- Step 1: Employee's Manager
(1, 2, 'Admin'),      -- Step 2: Finance (Assumed Admin has Finance permissions or is Finance team member for this example)
(1, 3, 'Admin');      -- Step 3: Director (Assumed Admin has Director permissions for this example)


-- 8.6. Insert Conditional Rules (Aligned with Admin UI mockup)
INSERT INTO ConditionalRules (company_id, name, rule_type, description, percentage_required, specific_approver_role, threshold_amount) VALUES
(1, 'Percentage Rule: 60%', 'Percentage', 'If 60% of all required approvers approve, the expense is approved.', 60, NULL, NULL),
(1, 'CFO Override Rule', 'SpecificApprover', 'If CFO (assumed Admin role) approves, expense is auto-approved.', NULL, 'Admin', NULL),
(1, 'Threshold Rule: > $5000', 'Threshold', 'Expenses > $5,000 automatically require Director (Admin) approval.', NULL, NULL, 5000.00);


-- 8.7. Insert Approval Transaction History for Approved/Rejected expenses

-- Mike Chen's Rejected Expense (E-3)
INSERT INTO ApprovalTransactions (expense_id, approver_id, step_sequence, status, comments) VALUES
((SELECT expense_id FROM Expenses WHERE description LIKE 'Taxi Service%'), (SELECT user_id FROM Users WHERE full_name = 'Sarah Johnson'), 1, 'Rejected', 'Reason: Personal use is not reimbursable.');

-- Emily Davis's Approved Expense (E-2) - Step 1
INSERT INTO ApprovalTransactions (expense_id, approver_id, step_sequence, status, comments) VALUES
((SELECT expense_id FROM Expenses WHERE description LIKE 'Flight to NYC%'), (SELECT user_id FROM Users WHERE full_name = 'Sarah Johnson'), 1, 'Approved', 'Approved travel cost. Receipt attached.');

-- Emily Davis's Approved Expense (E-2) - Step 2 (Finalized)
INSERT INTO ApprovalTransactions (expense_id, approver_id, step_sequence, status, comments) VALUES
((SELECT expense_id FROM Expenses WHERE description LIKE 'Flight to NYC%'), (SELECT user_id FROM Users WHERE full_name = 'John Doe'), 2, 'Approved', 'Finance processed and finalized.');

-- End of script
