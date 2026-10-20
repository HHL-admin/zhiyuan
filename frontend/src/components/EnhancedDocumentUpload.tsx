import React, { useState, useRef } from 'react';
import './EnhancedDocumentUpload.css';

interface EnhancedDocumentUploadProps {
  onUpload: (file: File) => void;
}

const EnhancedDocumentUpload: React.FC<EnhancedDocumentUploadProps> = ({ onUpload }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div
      className={`enhanced-upload-zone ${isDragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />

      <div className="upload-icon-container">
        <div className="upload-icon-ring"></div>
        <div className="upload-icon-ring"></div>
        <div className="upload-icon">📄</div>
      </div>

      {uploading ? (
        <div className="upload-text">
          <div className="upload-title">上传中...</div>
          <div className="upload-subtitle">请稍候</div>
        </div>
      ) : (
        <div className="upload-text">
          <div className="upload-title">拖拽文件到此处或点击上传</div>
          <div className="upload-subtitle">支持 PDF、Word(.docx)、TXT、Markdown 格式</div>
        </div>
      )}

      {uploading && (
        <div className="upload-progress-ring">
          <svg className="progress-svg" viewBox="0 0 100 100">
            <circle
              className="progress-circle-bg"
              cx="50"
              cy="50"
              r="40"
            />
            <circle
              className="progress-circle"
              cx="50"
              cy="50"
              r="40"
            />
          </svg>
        </div>
      )}
    </div>
  );
};

export default EnhancedDocumentUpload;
