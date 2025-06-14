class ZeytinAnaliz {
    constructor() {
        this.selectedFiles = [];
        this.currentAnalysisId = null;
        this.gpuAvailable = false;
        this.initializeEventListeners();
        this.checkGPUStatus();
    }

    initializeEventListeners() {
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');

        // Upload area click
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            this.handleFileSelection(e.target.files);
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            this.handleFileSelection(e.dataTransfer.files);
        });

        // Upload button
        uploadBtn.addEventListener('click', () => {
            this.uploadFiles();
        });
    }

    async checkGPUStatus() {
        try {
            const response = await fetch('/gpu-durum');
            const result = await response.json();
            
            if (result.success) {
                this.gpuAvailable = result.gpu_status.gpu_available;
                this.updateGPUStatusDisplay(result.gpu_status);
                
                if (this.gpuAvailable) {
                    document.getElementById('gpuModeOption').style.display = 'block';
                }
            }
        } catch (error) {
            console.error('GPU status check error:', error);
            this.updateGPUStatusDisplay({ gpu_available: false });
        }
    }

    updateGPUStatusDisplay(gpuStatus) {
        const gpuStatusElement = document.getElementById('gpuStatus');
        const gpuStatusText = document.getElementById('gpuStatusText');
        
        if (gpuStatus.gpu_available) {
            gpuStatusElement.className = 'gpu-status gpu-available';
            gpuStatusText.textContent = `GPU mevcut: ${gpuStatus.gpu_info?.device_name || 'Bilinmeyen GPU'}`;
        } else {
            gpuStatusElement.className = 'gpu-status gpu-unavailable';
            gpuStatusText.textContent = 'GPU mevcut değil - CPU modu kullanılacak';
        }
    }

    handleFileSelection(files) {
        this.selectedFiles = Array.from(files);
        this.displaySelectedFiles();
        this.updateUploadButton();
        
        // Show analysis mode selection if files are selected
        if (this.selectedFiles.length > 0) {
            document.getElementById('analysisModeSection').style.display = 'block';
        } else {
            document.getElementById('analysisModeSection').style.display = 'none';
        }
    }

    displaySelectedFiles() {
        const fileList = document.getElementById('fileList');
        const selectedFilesList = document.getElementById('selectedFiles');

        if (this.selectedFiles.length > 0) {
            fileList.style.display = 'block';
            selectedFilesList.innerHTML = '';

            this.selectedFiles.forEach(file => {
                const fileType = this.getFileType(file.name);
                const li = document.createElement('li');
                li.innerHTML = `
                    <i class="fas ${fileType === 'RGB' ? 'fa-file-image' : 'fa-file-alt'}"></i>
                    <span>${file.name}</span>
                    <span style="margin-left: auto; color: #666;">${this.formatFileSize(file.size)}</span>
                    <span style="margin-left: 10px; padding: 2px 8px; background: ${fileType === 'RGB' ? '#3498db' : '#e67e22'}; color: white; border-radius: 10px; font-size: 0.8rem;">${fileType}</span>
                `;
                selectedFilesList.appendChild(li);
            });
        } else {
            fileList.style.display = 'none';
        }
    }

    getFileType(filename) {
        const extension = filename.split('.').pop().toLowerCase();
        return ['jpg', 'jpeg', 'png'].includes(extension) ? 'RGB' : 'Multispektral';
    }

    updateUploadButton() {
        const uploadBtn = document.getElementById('uploadBtn');
        uploadBtn.disabled = this.selectedFiles.length === 0;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getSelectedAnalysisMode() {
        const selectedMode = document.querySelector('input[name="analysisMode"]:checked');
        return selectedMode ? selectedMode.value : 'cpu';
    }

    async uploadFiles() {
        if (this.selectedFiles.length === 0) return;

        const uploadBtn = document.getElementById('uploadBtn');
        const originalText = uploadBtn.innerHTML;
        
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yükleniyor...';
        uploadBtn.disabled = true;

        try {
            const formData = new FormData();
            this.selectedFiles.forEach(file => {
                formData.append('dosyalar', file);
            });

            const response = await fetch('/analiz/yukle', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.currentAnalysisId = result.analiz_id;
                this.showMessage('Dosyalar başarıyla yüklendi!', 'success');
                
                // Show GPU availability info if relevant
                if (result.gpu_mevcut && !this.gpuAvailable) {
                    this.showMessage('GPU tespit edildi ancak kullanıma hazır değil', 'warning');
                }
                
                this.startAnalysis();
            } else {
                throw new Error(result.mesaj || 'Yükleme hatası');
            }

        } catch (error) {
            console.error('Upload error:', error);
            this.showMessage('Dosya yükleme hatası: ' + error.message, 'error');
        } finally {
            uploadBtn.innerHTML = originalText;
            uploadBtn.disabled = false;
        }
    }

    async startAnalysis() {
        if (!this.currentAnalysisId) return;

        const analysisMode = this.getSelectedAnalysisMode();
        
        // Show analysis section
        const analysisSection = document.getElementById('analysisSection');
        analysisSection.style.display = 'block';
        analysisSection.scrollIntoView({ behavior: 'smooth' });

        // Update analysis mode badge
        const analysisModeBadge = document.getElementById('analysisModeBadge');
        analysisModeBadge.textContent = analysisMode.toUpperCase();
        analysisModeBadge.className = `analysis-mode-badge ${analysisMode}`;

        // Update progress text
        const analysisProgress = document.getElementById('analysisProgress');
        analysisProgress.textContent = `${analysisMode.toUpperCase()} modu ile analiz başlatılıyor...`;

        const startTime = Date.now();

        try {
            const formData = new FormData();
            formData.append('analiz_id', this.currentAnalysisId);
            formData.append('analiz_modu', analysisMode);

            const response = await fetch('/analiz/baslat', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                const endTime = Date.now();
                const analysisTime = ((endTime - startTime) / 1000).toFixed(2);
                
                // Update analysis time badge
                document.getElementById('analysisTime').textContent = `${analysisTime}s`;
                
                this.displayAnalysisResults(result.sonuc);
                
                // Show performance comparison message
                if (analysisMode === 'cpu' && this.gpuAvailable) {
                    this.showMessage('Analiz CPU ile tamamlandı. GPU modu ile daha hızlı sonuç alabilirsiniz.', 'info');
                } else if (analysisMode === 'gpu') {
                    this.showMessage('Analiz GPU ile hızlandırılmış olarak tamamlandı!', 'success');
                }
            } else {
                throw new Error(result.mesaj || 'Analiz hatası');
            }

        } catch (error) {
            console.error('Analysis error:', error);
            this.showMessage('Analiz hatası: ' + error.message, 'error');
        }
    }

    displayAnalysisResults(sonuc) {
        // Hide loading, show results
        document.getElementById('analysisStatus').style.display = 'none';
        document.getElementById('analysisResults').style.display = 'block';

        // Update result values
        document.getElementById('toplamAgac').textContent = sonuc.toplam_agac;
        document.getElementById('toplamZeytin').textContent = sonuc.toplam_zeytin;
        document.getElementById('tahminiMiktar').textContent = sonuc.tahmini_zeytin_miktari.toFixed(2) + ' kg';
        document.getElementById('saglikDurumu').textContent = sonuc.saglik_durumu;

        // Update NDVI values
        document.getElementById('ndviValue').textContent = sonuc.ndvi_ortalama.toFixed(3);
        document.getElementById('gndviValue').textContent = sonuc.gndvi_ortalama.toFixed(3);
        document.getElementById('ndreValue').textContent = sonuc.ndre_ortalama.toFixed(3);

        // Update performance info
        document.getElementById('performanceTime').textContent = `${sonuc.analiz_suresi?.toFixed(2) || 'N/A'} saniye`;
        document.getElementById('performanceDevice').textContent = sonuc.kullanilan_cihaz?.toUpperCase() || 'CPU';
        document.getElementById('performanceFiles').textContent = `${sonuc.detaylar?.length || 0} dosya`;

        // Show detailed performance info for each file
        if (sonuc.detaylar && sonuc.detaylar.length > 0) {
            let totalProcessingTime = 0;
            sonuc.detaylar.forEach(detay => {
                if (detay.isleme_suresi) {
                    totalProcessingTime += detay.isleme_suresi;
                }
            });
            
            if (totalProcessingTime > 0) {
                const avgTimePerFile = (totalProcessingTime / sonuc.detaylar.length).toFixed(2);
                this.showMessage(`Ortalama dosya başına işlem süresi: ${avgTimePerFile} saniye (${sonuc.kullanilan_cihaz?.toUpperCase()})`, 'info');
            }
        }

        this.showMessage('Analiz başarıyla tamamlandı!', 'success');
    }

    showMessage(text, type) {
        // Remove existing messages
        const existingMessages = document.querySelectorAll('.message');
        existingMessages.forEach(msg => msg.remove());

        // Create new message
        const message = document.createElement('div');
        message.className = `message ${type}`;
        message.textContent = text;

        // Insert after header
        const header = document.querySelector('.header');
        header.insertAdjacentElement('afterend', message);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (message.parentNode) {
                message.remove();
            }
        }, 5000);
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    new ZeytinAnaliz();
});