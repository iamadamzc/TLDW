// TL;DW Frontend JavaScript

class TLDWApp {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateSummarizeButtonState();
    }

    bindEvents() {
        // Playlist selection
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.addEventListener('change', (e) => {
                this.handlePlaylistChange(e.target.value);
            });
        }

        // Video checkbox selection
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('video-checkbox')) {
                this.updateSummarizeButtonState();
                this.updateSelectAllState();
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.handleSelectAll(e.target.checked);
            });
        }

        // Summarize button
        const summarizeBtn = document.getElementById('summarize-btn');
        if (summarizeBtn) {
            summarizeBtn.addEventListener('click', () => {
                this.handleSummarize();
            });
        }
    }

    async handlePlaylistChange(playlistId) {
        if (!playlistId) {
            this.hideVideosSection();
            return;
        }

        try {
            this.showLoading();
            
            const response = await fetch('/api/select-playlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ playlist_id: playlistId })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.displayVideos(data.videos);
                this.showVideosSection();
            } else {
                this.showAlert('error', data.error || 'Failed to load playlist videos');
            }
        } catch (error) {
            console.error('Error loading playlist:', error);
            this.showAlert('error', 'Network error. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    displayVideos(videos) {
        const videosList = document.getElementById('videos-list');
        if (!videosList || !videos.length) return;

        videosList.innerHTML = '';
        
        videos.forEach(video => {
            const videoCard = this.createVideoCard(video);
            videosList.appendChild(videoCard);
        });

        // Reinitialize Feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    createVideoCard(video) {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4';
        
        col.innerHTML = `
            <div class="video-card fade-in">
                <div class="form-check">
                    <input class="form-check-input video-checkbox" 
                           type="checkbox" 
                           value="${video.id}" 
                           id="video-${video.id}">
                    <label class="form-check-label w-100" for="video-${video.id}">
                        <div class="video-thumbnail">
                            <img src="${video.thumbnail}" alt="Thumbnail" class="img-fluid">
                            <div class="video-overlay">
                                <i data-feather="play" class="play-icon"></i>
                            </div>
                        </div>
                        <div class="video-info">
                            <h6 class="video-title">${this.escapeHtml(video.title)}</h6>
                            <small class="text-muted">${this.escapeHtml(video.channel_title)}</small>
                        </div>
                    </label>
                </div>
            </div>
        `;
        
        return col;
    }

    handleSelectAll(checked) {
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');
        videoCheckboxes.forEach(checkbox => {
            checkbox.checked = checked;
        });
        this.updateSummarizeButtonState();
    }

    updateSelectAllState() {
        const selectAllCheckbox = document.getElementById('select-all');
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');
        
        if (!selectAllCheckbox || !videoCheckboxes.length) return;

        const checkedCount = document.querySelectorAll('.video-checkbox:checked').length;
        const totalCount = videoCheckboxes.length;

        selectAllCheckbox.checked = checkedCount === totalCount;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
    }

    updateSummarizeButtonState() {
        const summarizeBtn = document.getElementById('summarize-btn');
        const checkedVideos = document.querySelectorAll('.video-checkbox:checked');
        
        if (summarizeBtn) {
            summarizeBtn.disabled = checkedVideos.length === 0;
            
            if (checkedVideos.length > 0) {
                summarizeBtn.innerHTML = `
                    <i data-feather="zap"></i> 
                    Summarize ${checkedVideos.length} Video${checkedVideos.length !== 1 ? 's' : ''} with TL;DW
                `;
            } else {
                summarizeBtn.innerHTML = `
                    <i data-feather="zap"></i> 
                    Summarize with TL;DW
                `;
            }
            
            // Reinitialize Feather icons
            if (typeof feather !== 'undefined') {
                feather.replace();
            }
        }
    }

    async handleSummarize(videoIds) {
        this.showLoadingModal();
        try {
            const res = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_ids: videoIds })
            });

            const ct = res.headers.get('content-type') || '';
            const body = await res.text();

            if (!res.ok) {
                this.hideLoadingModal();
                throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
            }

            const data = ct.includes('application/json') ? JSON.parse(body) : {};
            this.showToast(data.message || 'Request received — we’ll email you when it’s ready.');
            this.clearVideoSelection();
            this.hideLoadingModal();
        } catch (err) {
            console.error(err);
            this.showToast('Failed to start the job. Please try again.');
            this.hideLoadingModal();
        }
    }

    clearVideoSelection() {
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');
        const selectAllCheckbox = document.getElementById('select-all');
        
        videoCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
        
        this.updateSummarizeButtonState();
    }

    showVideosSection() {
        const videosSection = document.getElementById('videos-section');
        if (videosSection) {
            videosSection.style.display = 'block';
            videosSection.classList.add('slide-up');
        }
    }

    hideVideosSection() {
        const videosSection = document.getElementById('videos-section');
        if (videosSection) {
            videosSection.style.display = 'none';
        }
    }

    showLoadingModal() {
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }

    hideLoadingModal() {
        const modalElement = document.getElementById('loadingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }
    }

    showLoading() {
        // Add loading state to playlist select or other UI elements
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.disabled = true;
        }
    }

    hideLoading() {
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.disabled = false;
        }
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;

        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div class="toast" role="alert" aria-live="assertive" aria-atomic="true" id="${toastId}">
                <div class="toast-header">
                    <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${this.escapeHtml(message)}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TLDWApp();
});

// Handle page visibility changes to refresh tokens if needed
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && window.location.pathname.includes('dashboard')) {
        // Optionally refresh data when user returns to tab
        console.log('Tab became visible - could refresh data here');
    }
});

// Updated async job processing functions
TLDWApp.prototype.handleSummarizeAsync = async function() {
    const checkedVideos = document.querySelectorAll('.video-checkbox:checked');
    if (checkedVideos.length === 0) {
        this.showAlert('warning', 'Please select at least one video to summarize.');
        return;
    }

    const videoIds = Array.from(checkedVideos).map(checkbox => checkbox.value);
    
    // Show job submission confirmation instead of processing spinner
    this.showJobSubmissionModal(videoIds.length);
    
    try {
        const response = await fetch('/api/summarize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_ids: videoIds })
        });

        const data = await response.json();

        if (response.status === 202) {
            // Successful job submission
            this.handleJobSubmissionSuccess(data);
        } else if (response.status === 400) {
            // Validation error
            this.handleJobSubmissionError('Invalid request: ' + (data.error || 'Please check your video selection.'));
        } else if (response.status === 429) {
            // Rate limiting
            this.handleJobSubmissionError('Too many requests. Please wait a moment before trying again.');
        } else if (response.status === 500) {
            // Server error
            this.handleJobSubmissionError('Server error occurred. Please try again later.');
        } else {
            // Other errors
            this.handleJobSubmissionError(data.error || `Unexpected error (${response.status})`);
        }
    } catch (error) {
        console.error('Network error:', error);
        this.handleJobSubmissionError('Network error. Please check your connection and try again.');
    }
};

TLDWApp.prototype.handleJobSubmissionSuccess = function(data) {
    this.hideJobSubmissionModal();
    
    // Show success message with job details
    const message = data.message || 'Job submitted successfully! You\'ll receive an email when processing is complete.';
    this.showAlert('success', message);
    
    // If job_id is provided, start status monitoring
    if (data.job_id) {
        this.startJobStatusMonitoring(data.job_id);
    }
    
    // Clear video selection
    this.clearVideoSelection();
    
    // Show job status card
    this.showJobStatusCard(data.job_id, data.video_count || 0);
};

TLDWApp.prototype.handleJobSubmissionError = function(errorMessage) {
    this.hideJobSubmissionModal();
    this.showAlert('error', errorMessage);
};

TLDWApp.prototype.showJobSubmissionModal = function(videoCount) {
    // Update the loading modal for job submission
    const modal = document.getElementById('loadingModal');
    const modalBody = modal.querySelector('.modal-body');
    
    modalBody.innerHTML = `
        <div class="text-center p-4">
            <div class="spinner-border text-primary mb-3" role="status">
                <span class="visually-hidden">Submitting...</span>
            </div>
            <h5>Submitting Your Job</h5>
            <p class="text-muted mb-0">Processing ${videoCount} video${videoCount !== 1 ? 's' : ''}...</p>
            <small class="text-muted">This should only take a moment</small>
        </div>
    `;
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
};

TLDWApp.prototype.hideJobSubmissionModal = function() {
    const modalElement = document.getElementById('loadingModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
};

TLDWApp.prototype.showJobStatusCard = function(jobId, videoCount) {
    // Create or update job status card
    let statusCard = document.getElementById('job-status-card');
    
    if (!statusCard) {
        statusCard = document.createElement('div');
        statusCard.id = 'job-status-card';
        statusCard.className = 'card mb-4 border-primary';
        
        // Insert after alert container
        const alertContainer = document.getElementById('alert-container');
        alertContainer.parentNode.insertBefore(statusCard, alertContainer.nextSibling);
    }
    
    statusCard.innerHTML = `
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h5 class="card-title mb-1">
                        <i data-feather="clock" class="text-primary"></i> 
                        Job in Progress
                    </h5>
                    <p class="text-muted mb-0">
                        Processing ${videoCount} video${videoCount !== 1 ? 's' : ''} • Job ID: ${jobId}
                    </p>
                    <small class="text-muted">
                        <span id="job-status-text">Initializing...</span>
                    </small>
                </div>
                <div>
                    <button class="btn btn-outline-primary btn-sm" onclick="app.checkJobStatus('${jobId}')">
                        <i data-feather="refresh-cw"></i> Check Status
                    </button>
                </div>
            </div>
            <div class="progress mt-3" style="height: 6px;">
                <div id="job-progress-bar" class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" style="width: 10%"></div>
            </div>
        </div>
    `;
    
    // Reinitialize Feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
};

TLDWApp.prototype.startJobStatusMonitoring = function(jobId) {
    // Poll job status every 10 seconds
    const pollInterval = 10000; // 10 seconds
    let attempts = 0;
    const maxAttempts = 60; // 10 minutes maximum
    
    const poll = async () => {
        attempts++;
        
        try {
            const status = await this.checkJobStatus(jobId, false); // Don't show manual feedback
            
            if (status && (status.status === 'completed' || status.status === 'failed')) {
                // Job finished, stop polling
                this.handleJobCompletion(jobId, status);
                return;
            }
            
            // Continue polling if job is still running and we haven't exceeded max attempts
            if (attempts < maxAttempts) {
                setTimeout(poll, pollInterval);
            } else {
                // Timeout - stop polling but don't remove status card
                this.updateJobStatusText('Status monitoring timed out. Check your email for completion notification.');
            }
            
        } catch (error) {
            console.error('Error polling job status:', error);
            // Continue polling on error, but reduce frequency
            if (attempts < maxAttempts) {
                setTimeout(poll, pollInterval * 2);
            }
        }
    };
    
    // Start polling after a short delay
    setTimeout(poll, 3000);
};

TLDWApp.prototype.checkJobStatus = async function(jobId, showFeedback = true) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        const data = await response.json();
        
        if (response.ok) {
            this.updateJobStatusDisplay(data);
            
            if (showFeedback) {
                const statusMessage = this.getStatusMessage(data);
                this.showAlert('info', statusMessage);
            }
            
            return data;
        } else {
            if (showFeedback) {
                this.showAlert('error', data.error || 'Failed to check job status');
            }
            return null;
        }
    } catch (error) {
        console.error('Error checking job status:', error);
        if (showFeedback) {
            this.showAlert('error', 'Network error while checking job status');
        }
        return null;
    }
};

// Global app instance for onclick handlers
let app;

// Update the initialization to use the new async handler
document.addEventListener('DOMContentLoaded', () => {
    app = new TLDWApp();
    
    // Override the handleSummarize method with the async version
    app.handleSummarize = app.handleSummarizeAsync;
});TLDWAp
p.prototype.updateJobStatusDisplay = function(jobData) {
    const statusText = document.getElementById('job-status-text');
    const progressBar = document.getElementById('job-progress-bar');
    
    if (statusText) {
        statusText.textContent = this.getStatusMessage(jobData);
    }
    
    if (progressBar) {
        const progress = this.calculateProgress(jobData);
        progressBar.style.width = `${progress}%`;
        
        // Update progress bar class based on status
        progressBar.className = 'progress-bar';
        if (jobData.status === 'completed') {
            progressBar.classList.add('bg-success');
        } else if (jobData.status === 'failed') {
            progressBar.classList.add('bg-danger');
        } else {
            progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
        }
    }
};

TLDWApp.prototype.getStatusMessage = function(jobData) {
    switch (jobData.status) {
        case 'queued':
            return 'Job queued, waiting to start...';
        case 'processing':
            const processed = jobData.videos_processed || 0;
            const total = jobData.total_videos || 0;
            return `Processing videos... (${processed}/${total} completed)`;
        case 'completed':
            const successful = jobData.successful_videos || 0;
            const totalVids = jobData.total_videos || 0;
            return `Completed! ${successful}/${totalVids} videos processed successfully. Check your email.`;
        case 'failed':
            return 'Job failed. Please try again or contact support.';
        default:
            return 'Status unknown';
    }
};

TLDWApp.prototype.calculateProgress = function(jobData) {
    switch (jobData.status) {
        case 'queued':
            return 5;
        case 'processing':
            const processed = jobData.videos_processed || 0;
            const total = jobData.total_videos || 1;
            return Math.max(10, Math.min(90, (processed / total) * 80 + 10));
        case 'completed':
            return 100;
        case 'failed':
            return 100;
        default:
            return 10;
    }
};

TLDWApp.prototype.handleJobCompletion = function(jobId, jobData) {
    // Update the job status card to show completion
    const statusCard = document.getElementById('job-status-card');
    if (statusCard) {
        const isSuccess = jobData.status === 'completed';
        const cardClass = isSuccess ? 'border-success' : 'border-danger';
        const iconClass = isSuccess ? 'check-circle text-success' : 'x-circle text-danger';
        const title = isSuccess ? 'Job Completed' : 'Job Failed';
        
        statusCard.className = `card mb-4 ${cardClass}`;
        statusCard.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="card-title mb-1">
                            <i data-feather="${iconClass.split(' ')[0]}" class="${iconClass.split(' ')[1]}"></i> 
                            ${title}
                        </h5>
                        <p class="text-muted mb-0">
                            Job ID: ${jobId}
                        </p>
                        <small class="text-muted">
                            ${this.getStatusMessage(jobData)}
                        </small>
                    </div>
                    <div>
                        <button class="btn btn-outline-secondary btn-sm" onclick="app.dismissJobStatus()">
                            <i data-feather="x"></i> Dismiss
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Reinitialize Feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }
    
    // Show completion alert
    if (jobData.status === 'completed') {
        this.showAlert('success', 'Job completed successfully! Check your email for the summary digest.');
    } else {
        this.showAlert('error', 'Job failed to complete. Please try again or contact support.');
    }
};

TLDWApp.prototype.dismissJobStatus = function() {
    const statusCard = document.getElementById('job-status-card');
    if (statusCard) {
        statusCard.remove();
    }
};

TLDWApp.prototype.updateJobStatusText = function(text) {
    const statusText = document.getElementById('job-status-text');
    if (statusText) {
        statusText.textContent = text;
    }
};

// Add showAlert method if it doesn't exist
TLDWApp.prototype.showAlert = function(type, message) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;

    const alertId = 'alert-' + Date.now();
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';

    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert" id="${alertId}">
            <strong>${type.charAt(0).toUpperCase() + type.slice(1)}:</strong> ${this.escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    alertContainer.insertAdjacentHTML('beforeend', alertHtml);
    
    // Auto-dismiss after 10 seconds for success/info alerts
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            const alertElement = document.getElementById(alertId);
            if (alertElement) {
                const alert = new bootstrap.Alert(alertElement);
                alert.close();
            }
        }, 10000);
    }
};