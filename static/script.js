// Check authentication on page load
window.addEventListener('load', () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/static/auth.html';
        return;
    }

    // Verify token is valid
    fetch('/api/auth/me', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => {
        if (!response.ok) {
            localStorage.removeItem('access_token');
            window.location.href = '/static/auth.html';
        }
    })
    .catch(() => {
        localStorage.removeItem('access_token');
        window.location.href = '/static/auth.html';
    });
});

// DOM Elements
const textTab = document.getElementById('text-tab');
const fileTab = document.getElementById('file-tab');
const medicalNoteTextarea = document.getElementById('medical-note');
const fileInput = document.getElementById('file-input');
const fileNameDisplay = document.getElementById('file-name');
const modelSelect = document.getElementById('model-select');
const extractBtn = document.getElementById('extract-btn');
const resultsSection = document.getElementById('results-section');
const resultsContent = document.getElementById('results-content');
const entityCount = document.getElementById('entity-count');
const downloadJsonBtn = document.getElementById('download-json-btn');
const clearBtn = document.getElementById('clear-btn');
const errorMessage = document.getElementById('error-message');
const highlightedText = document.getElementById('highlighted-text');

// Store original text for highlighting
let originalText = '';

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.getAttribute('data-tab');

        // Update active tab button
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tabName}-tab`).classList.add('active');
    });
});

// File upload handling
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        fileNameDisplay.textContent = `Selected: ${file.name}`;
    }
});

// Drag and drop
const fileUploadArea = document.querySelector('.file-upload');
fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadArea.style.borderColor = 'var(--primary-color)';
});

fileUploadArea.addEventListener('dragleave', () => {
    fileUploadArea.style.borderColor = 'var(--border-color)';
});

fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadArea.style.borderColor = 'var(--border-color)';

    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.txt') || file.name.endsWith('.pdf'))) {
        fileInput.files = e.dataTransfer.files;
        fileNameDisplay.textContent = `Selected: ${file.name}`;
    }
});

// Extract button handler
extractBtn.addEventListener('click', async () => {
    hideError();

    // Determine if using text or file input
    const isTextTab = textTab.classList.contains('active');

    if (isTextTab) {
        const text = medicalNoteTextarea.value.trim();
        if (!text) {
            showError('Please enter a medical note');
            return;
        }
        await extractFromText(text);
    } else {
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a file');
            return;
        }
        await extractFromFile(file);
    }
});

// Extract from text
async function extractFromText(text) {
    setLoading(true);
    originalText = text; // Store original text for highlighting

    try {
        const token = localStorage.getItem('access_token');

        const response = await fetch('/api/uscdi/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                medical_note: text,
                model: modelSelect.value
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Extraction failed');
        }

        const data = await response.json();
        displayUSCDIResults(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

// Extract from file
async function extractFromFile(file) {
    setLoading(true);

    try {
        const token = localStorage.getItem('access_token');

        // For text files, read content to store as originalText
        // For PDFs, we'll get it from the response
        if (file.name.endsWith('.txt') || file.name.endsWith('.text')) {
            const fileContent = await file.text();
            originalText = fileContent;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('model', modelSelect.value);

        const response = await fetch(`/api/uscdi/extract-file?model=${modelSelect.value}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Extraction failed');
        }

        const data = await response.json();

        // For PDFs, use the original_text from the response
        if (file.name.endsWith('.pdf') && data.original_text) {
            originalText = data.original_text;
        }

        displayUSCDIResults(data);

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
    }
}

// Display results
let currentResults = null;

function displayResults(data) {
    currentResults = data;

    if (!data.success || !data.entities) {
        showError('No entities extracted');
        return;
    }

    const entities = data.entities;
    entityCount.textContent = `${data.total_entities} ${data.total_entities === 1 ? 'entity' : 'entities'}`;

    const categoryConfig = {
        disorders: { name: 'Disorders/Diseases', emoji: '🦠' },
        signs_symptoms: { name: 'Signs & Symptoms', emoji: '📊' },
        procedures: { name: 'Procedures', emoji: '⚕️' },
        medications: { name: 'Medications/Drugs', emoji: '💊' },
        anatomy: { name: 'Anatomical Structures', emoji: '🫀' },
        lab_results: { name: 'Laboratory Results', emoji: '🔬' },
        devices: { name: 'Medical Devices', emoji: '🩺' },
        organisms: { name: 'Organisms', emoji: '🦠' },
        substances: { name: 'Substances', emoji: '⚗️' },
        temporal: { name: 'Temporal Information', emoji: '📅' }
    };

    let html = '';

    for (const [key, config] of Object.entries(categoryConfig)) {
        const items = entities[key];
        if (items && items.length > 0) {
            html += `
                <div class="entity-category">
                    <div class="category-header">
                        <span>${config.emoji} ${config.name}</span>
                        <span class="category-count">${items.length}</span>
                    </div>
                    <div class="entity-list">
            `;

            items.forEach(entity => {
                html += `
                    <div class="entity-item">
                        <div class="entity-text">${escapeHtml(entity.text)}</div>
                `;

                if (entity.cui) {
                    html += `<div class="entity-detail"><strong>CUI:</strong> ${escapeHtml(entity.cui)}</div>`;
                }

                if (entity.value) {
                    html += `<div class="entity-detail"><strong>Value:</strong> ${escapeHtml(entity.value)}</div>`;
                }

                if (entity.context) {
                    html += `<div class="entity-detail"><strong>Context:</strong> ${escapeHtml(entity.context)}</div>`;
                }

                html += `</div>`;
            });

            html += `
                    </div>
                </div>
            `;
        }
    }

    resultsContent.innerHTML = html || '<p>No entities found</p>';
    resultsSection.style.display = 'block';

    // Generate highlighted text view
    generateHighlightedText(entities);

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Display USCDI results
function displayUSCDIResults(data) {
    currentResults = data;

    if (!data.success || !data.uscdi_data) {
        showError('No USCDI data extracted');
        return;
    }

    const uscdiData = data.uscdi_data;
    entityCount.textContent = `${data.data_classes_count} USCDI data classes`;

    // Map of USCDI v6 data class names to display config (all 22 classes)
    const uscdiClassConfig = {
        patient_demographics: { name: 'Patient Demographics', emoji: '👤' },
        allergies_and_intolerances: { name: 'Allergies & Intolerances', emoji: '⚠️' },
        care_plan: { name: 'Care Plan', emoji: '📋' },
        care_team_members: { name: 'Care Team Members', emoji: '👥' },
        clinical_notes: { name: 'Clinical Notes', emoji: '📝' },
        clinical_tests: { name: 'Clinical Tests', emoji: '🧪' },
        diagnostic_imaging: { name: 'Diagnostic Imaging', emoji: '🔍' },
        encounter_information: { name: 'Encounter Information', emoji: '🏥' },
        facility_information: { name: 'Facility Information', emoji: '🏢' },
        family_health_history: { name: 'Family Health History', emoji: '👨‍👩‍👧‍👦' },
        goals_and_preferences: { name: 'Goals & Preferences', emoji: '🎯' },
        health_insurance_information: { name: 'Health Insurance', emoji: '💳' },
        health_status_assessments: { name: 'Health Status Assessments', emoji: '📊' },
        immunizations: { name: 'Immunizations', emoji: '💉' },
        laboratory: { name: 'Laboratory Results', emoji: '🔬' },
        medical_devices: { name: 'Medical Devices', emoji: '🔧' },
        medications: { name: 'Medications', emoji: '💊' },
        orders: { name: 'Orders', emoji: '📑' },
        problems: { name: 'Problems/Diagnoses', emoji: '🩺' },
        procedures: { name: 'Procedures', emoji: '⚕️' },
        provenance: { name: 'Provenance', emoji: '📄' },
        vital_signs: { name: 'Vital Signs', emoji: '💓' }
    };

    let html = '';

    for (const [key, value] of Object.entries(uscdiData)) {
        if (key.startsWith('_') || !value || (Array.isArray(value) && value.length === 0) || (typeof value === 'object' && Object.keys(value).length === 0)) {
            continue;
        }

        const config = uscdiClassConfig[key] || { name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), emoji: '📌' };

        html += `
            <div class="entity-category">
                <div class="category-header">
                    <span>${config.emoji} ${config.name}</span>
                </div>
                <div class="entity-list">
        `;

        if (Array.isArray(value)) {
            value.forEach(item => {
                html += `
                    <div class="entity-item">
                        <pre style="background: #f8fafc; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.9rem;">${escapeHtml(JSON.stringify(item, null, 2))}</pre>
                    </div>
                `;
            });
        } else if (typeof value === 'object') {
            html += `
                <div class="entity-item">
                    <pre style="background: #f8fafc; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.9rem;">${escapeHtml(JSON.stringify(value, null, 2))}</pre>
                </div>
            `;
        }

        html += `
                </div>
            </div>
        `;
    }

    resultsContent.innerHTML = html || '<p>No USCDI data found</p>';
    resultsSection.style.display = 'block';

    // Generate highlighted text for USCDI data
    generateUSCDIHighlightedText(uscdiData);

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Download JSON
downloadJsonBtn.addEventListener('click', () => {
    if (!currentResults) return;

    // Determine what data to download based on extraction type
    const dataToDownload = currentResults.uscdi_data || currentResults.entities || currentResults;
    const filename = currentResults.uscdi_data
        ? `uscdi-data-${new Date().toISOString().slice(0, 10)}.json`
        : `medical-entities-${new Date().toISOString().slice(0, 10)}.json`;

    const dataStr = JSON.stringify(dataToDownload, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
});

// Clear results
clearBtn.addEventListener('click', () => {
    resultsSection.style.display = 'none';
    resultsContent.innerHTML = '';
    currentResults = null;
});

// UI helpers
function setLoading(loading) {
    extractBtn.disabled = loading;
    const btnText = extractBtn.querySelector('.btn-text');
    const spinner = extractBtn.querySelector('.spinner');

    if (loading) {
        btnText.textContent = 'Extracting...';
        spinner.style.display = 'block';
    } else {
        btnText.textContent = 'Extract USCDI v6 Data';
        spinner.style.display = 'none';
    }
}

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    errorMessage.scrollIntoView({ behavior: 'smooth' });
}

function hideError() {
    errorMessage.style.display = 'none';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Generate highlighted text
function generateHighlightedText(entities) {
    if (!originalText) {
        highlightedText.innerHTML = '<p>Original text not available</p>';
        return;
    }

    // Entity type to CSS class mapping
    const entityTypeMap = {
        'disorders': 'disorder',
        'signs_symptoms': 'symptom',
        'procedures': 'procedure',
        'medications': 'medication',
        'lab_results': 'lab',
        'anatomy': 'anatomy',
        'devices': 'default',
        'organisms': 'default',
        'substances': 'default',
        'temporal': 'default'
    };

    // Collect all entities with their positions
    let entityMatches = [];

    for (const [category, items] of Object.entries(entities)) {
        if (!Array.isArray(items)) continue;

        const highlightClass = entityTypeMap[category] || 'default';

        items.forEach(entity => {
            const searchText = entity.text;
            let startIndex = 0;

            // Find all occurrences of this entity in the text
            while ((startIndex = originalText.toLowerCase().indexOf(searchText.toLowerCase(), startIndex)) !== -1) {
                entityMatches.push({
                    start: startIndex,
                    end: startIndex + searchText.length,
                    text: searchText,
                    class: highlightClass,
                    category: category,
                    entity: entity
                });
                startIndex += searchText.length;
            }
        });
    }

    // Sort by start position
    entityMatches.sort((a, b) => a.start - b.start);

    // Remove overlapping matches (keep first occurrence)
    let filteredMatches = [];
    let lastEnd = -1;
    for (const match of entityMatches) {
        if (match.start >= lastEnd) {
            filteredMatches.push(match);
            lastEnd = match.end;
        }
    }

    // Build highlighted HTML
    let highlightedHTML = '';
    let currentPos = 0;

    filteredMatches.forEach(match => {
        // Add text before the match
        if (currentPos < match.start) {
            highlightedHTML += escapeHtml(originalText.substring(currentPos, match.start));
        }

        // Add highlighted entity
        const tooltipText = match.entity.cui
            ? `${match.category.replace(/_/g, ' ')}: ${match.entity.cui}`
            : match.category.replace(/_/g, ' ');

        highlightedHTML += `<span class="highlight highlight-${match.class}" title="${escapeHtml(tooltipText)}">`;
        highlightedHTML += escapeHtml(originalText.substring(match.start, match.end));
        highlightedHTML += `<span class="highlight-tooltip">${escapeHtml(tooltipText)}</span>`;
        highlightedHTML += '</span>';

        currentPos = match.end;
    });

    // Add remaining text
    if (currentPos < originalText.length) {
        highlightedHTML += escapeHtml(originalText.substring(currentPos));
    }

    highlightedText.innerHTML = highlightedHTML || '<p>No text to display</p>';
}

// Generate highlighted text for USCDI extraction
function generateUSCDIHighlightedText(uscdiData) {
    console.log('generateUSCDIHighlightedText called', { originalTextLength: originalText ? originalText.length : 0, uscdiData });

    if (!originalText) {
        console.warn('No original text available for highlighting');
        highlightedText.innerHTML = '<p>Original text not available</p>';
        return;
    }

    // Collect all clinical terms from USCDI data
    let termsToHighlight = [];

    // Extract terms from different USCDI classes
    const classesToHighlight = {
        'problems': ['problem', 'name', 'condition', 'diagnosis', 'text', 'description'],
        'medications': ['medication', 'name', 'drug', 'text'],
        'allergies_and_intolerances': ['substance', 'allergen', 'name', 'text'],
        'procedures': ['procedure', 'name', 'text'],
        'vital_signs': ['measurement', 'name', 'text', 'type'],
        'laboratory': ['test', 'name', 'text'],
        'diagnostic_imaging': ['imaging_type', 'name', 'text', 'type'],
        'immunizations': ['vaccine', 'name', 'text'],
        'clinical_tests': ['test', 'name', 'text'],
        'family_health_history': ['condition', 'name', 'text'],
        'orders': ['order', 'name', 'text']
    };

    for (const [className, fields] of Object.entries(classesToHighlight)) {
        if (!uscdiData[className]) continue;

        const items = Array.isArray(uscdiData[className]) ? uscdiData[className] : [uscdiData[className]];

        items.forEach(item => {
            if (!item || typeof item !== 'object') return;

            // Try to find any field that contains a text value
            let foundText = null;
            for (const field of fields) {
                if (item[field] && typeof item[field] === 'string') {
                    foundText = item[field];
                    break;
                }
            }

            // If no specific field found, try any string field
            if (!foundText) {
                for (const [key, value] of Object.entries(item)) {
                    if (typeof value === 'string' && value.length > 2 && !key.startsWith('_')) {
                        foundText = value;
                        break;
                    }
                }
            }

            if (foundText) {
                termsToHighlight.push({
                    text: foundText,
                    class: className,
                    cui: item.umls_cui || null
                });
            }
        });
    }

    console.log(`Found ${termsToHighlight.length} terms to highlight`);

    if (termsToHighlight.length === 0) {
        console.warn('No terms found to highlight, showing plain text');
        highlightedText.innerHTML = `<p style="white-space: pre-wrap; font-family: monospace;">${escapeHtml(originalText)}</p>`;
        return;
    }

    // Find matches in original text
    let entityMatches = [];

    termsToHighlight.forEach(term => {
        const searchText = term.text;
        let startIndex = 0;

        while ((startIndex = originalText.toLowerCase().indexOf(searchText.toLowerCase(), startIndex)) !== -1) {
            entityMatches.push({
                start: startIndex,
                end: startIndex + searchText.length,
                text: searchText,
                class: term.class,
                cui: term.cui
            });
            startIndex += searchText.length;
        }
    });

    // Sort and remove overlaps
    entityMatches.sort((a, b) => a.start - b.start);
    let filteredMatches = [];
    let lastEnd = -1;
    for (const match of entityMatches) {
        if (match.start >= lastEnd) {
            filteredMatches.push(match);
            lastEnd = match.end;
        }
    }

    // Build highlighted HTML
    let highlightedHTML = '';
    let currentPos = 0;

    filteredMatches.forEach(match => {
        // Add text before match
        if (currentPos < match.start) {
            highlightedHTML += escapeHtml(originalText.substring(currentPos, match.start));
        }

        // Add highlighted term with color coding
        const classNameForDisplay = match.class.replace(/_/g, ' ');
        const tooltipText = match.cui ? `${classNameForDisplay} (CUI: ${match.cui})` : classNameForDisplay;
        const highlightClass = `highlight-${match.class}`; // e.g., highlight-problems, highlight-medications

        if (currentPos === match.start) { // Log first match for debugging
            console.log('First highlight:', { class: match.class, highlightClass, tooltipText });
        }

        highlightedHTML += `<span class="highlight ${highlightClass}" title="${escapeHtml(tooltipText)}">`;
        highlightedHTML += escapeHtml(originalText.substring(match.start, match.end));
        highlightedHTML += `<span class="highlight-tooltip">${escapeHtml(tooltipText)}</span>`;
        highlightedHTML += '</span>';

        currentPos = match.end;
    });

    // Add remaining text
    if (currentPos < originalText.length) {
        highlightedHTML += escapeHtml(originalText.substring(currentPos));
    }

    highlightedText.innerHTML = highlightedHTML || '<p>No text to display</p>';
}

// Tab switching for results views
document.querySelectorAll('.results-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const viewName = btn.getAttribute('data-view');

        // Update active tab button
        document.querySelectorAll('.results-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Update active view
        document.querySelectorAll('.results-view').forEach(view => {
            view.style.display = 'none';
        });

        if (viewName === 'structured') {
            document.getElementById('structured-view').style.display = 'block';
        } else if (viewName === 'highlighted') {
            document.getElementById('highlighted-view').style.display = 'block';
        }
    });
});

// Logout function
function logout() {
    localStorage.removeItem('access_token');
    window.location.href = '/static/auth.html';
}
