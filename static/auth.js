// Auth page JavaScript

// DOM Elements
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const errorMsg = document.getElementById('error-msg');
const successMsg = document.getElementById('success-msg');

// Tab switching
document.querySelectorAll('.auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.getAttribute('data-tab');

        // Update active tab
        document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        // Update active form
        document.querySelectorAll('.auth-form').forEach(form => {
            form.classList.remove('active');
        });
        document.getElementById(`${tabName}-form`).classList.add('active');

        // Clear messages
        hideError();
        hideSuccess();
    });
});

// Login form submission
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();
    hideSuccess();

    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    const loginBtn = document.getElementById('login-btn');
    loginBtn.disabled = true;
    loginBtn.querySelector('.btn-text').textContent = 'Logging in...';

    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch('/api/auth/login', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();

        // Store token
        localStorage.setItem('access_token', data.access_token);

        showSuccess('Login successful! Redirecting...');

        // Redirect to main page
        setTimeout(() => {
            window.location.href = '/';
        }, 1000);

    } catch (error) {
        showError(error.message);
    } finally {
        loginBtn.disabled = false;
        loginBtn.querySelector('.btn-text').textContent = 'Login';
    }
});

// Register form submission
registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    hideError();
    hideSuccess();

    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;

    // Validate passwords match
    if (password !== confirmPassword) {
        showError('Passwords do not match');
        return;
    }

    // Validate password length
    if (password.length < 8) {
        showError('Password must be at least 8 characters long');
        return;
    }

    const registerBtn = document.getElementById('register-btn');
    registerBtn.disabled = true;
    registerBtn.querySelector('.btn-text').textContent = 'Creating account...';

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                email,
                password
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }

        showSuccess('Account created successfully! Please login.');

        // Switch to login tab after 2 seconds
        setTimeout(() => {
            document.querySelector('.auth-tab[data-tab="login"]').click();
            document.getElementById('login-username').value = username;
        }, 2000);

    } catch (error) {
        showError(error.message);
    } finally {
        registerBtn.disabled = false;
        registerBtn.querySelector('.btn-text').textContent = 'Create Account';
    }
});

// Helper functions
function showError(message) {
    errorMsg.textContent = message;
    errorMsg.style.display = 'block';
}

function hideError() {
    errorMsg.style.display = 'none';
}

function showSuccess(message) {
    successMsg.textContent = message;
    successMsg.style.display = 'block';
}

function hideSuccess() {
    successMsg.style.display = 'none';
}

// Check if already logged in
window.addEventListener('load', () => {
    const token = localStorage.getItem('access_token');
    if (token) {
        // Verify token is valid
        fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => {
            if (response.ok) {
                window.location.href = '/';
            } else {
                localStorage.removeItem('access_token');
            }
        })
        .catch(() => {
            localStorage.removeItem('access_token');
        });
    }
});
