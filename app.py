import html
import io
import json
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
from jinja2 import Template
import pandas as pd

from backend.llm_service import DEFAULT_OPENAI_MODEL
from backend.scanner import scan_paths
from backend.rag import retrieve
from backend.validators import run_terraform_validate
from backend.utils.env import load_env_file
from backend.utils.logging import get_logger, setup_logging
from backend.utils.settings import get_llm_settings, update_llm_settings

load_env_file()
setup_logging(service="terraform-manager-ui")
LOGGER = get_logger(__name__)

APP_TITLE = "TerraformManager — Wizard + Reviewer (Extended)"
BASE_DIR = Path(__file__).resolve().parent
GEN_DIR = BASE_DIR / "generated"
GEN_DIR.mkdir(exist_ok=True)

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
KNOWLEDGE_DOC_COUNT = (
    sum(1 for _ in KNOWLEDGE_DIR.rglob("*.md")) if KNOWLEDGE_DIR.exists() else 0
)

CUSTOM_PAGE_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    /* Enhanced color palette */
    --tm-primary: #3b82f6;
    --tm-primary-hover: #2563eb;
    --tm-primary-light: #dbeafe;
    --tm-primary-dark: #1e40af;
    --tm-secondary: #8b5cf6;
    --tm-accent: #06b6d4;
    
    --tm-surface: #1e293b;
    --tm-surface-light: #334155;
    --tm-surface-lighter: #475569;
    --tm-surface-ambient: #f8fafc;
    --tm-surface-ambient-alt: #e2e8f0;
    --tm-background: #0f172a;
    --tm-background-alt: #1a1f2e;
    
    --tm-border: rgba(148, 163, 184, 0.15);
    --tm-border-strong: rgba(148, 163, 184, 0.3);
    --tm-border-focus: rgba(59, 130, 246, 0.5);
    
    --tm-text-primary: #f1f5f9;
    --tm-text-secondary: #cbd5e1;
    --tm-text-muted: #94a3b8;
    --tm-text-on-light: #0f172a;
    --tm-text-muted-light: #475569;
    
    --tm-success: #10b981;
    --tm-success-bg: rgba(16, 185, 129, 0.1);
    --tm-warning: #f59e0b;
    --tm-warning-bg: rgba(245, 158, 11, 0.1);
    --tm-error: #ef4444;
    --tm-error-bg: rgba(239, 68, 68, 0.1);
    --tm-info: #3b82f6;
    --tm-info-bg: rgba(59, 130, 246, 0.1);
    
    --tm-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    --tm-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    --tm-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
    --tm-shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
    --tm-shadow-glow: 0 0 20px rgba(59, 130, 246, 0.3);
    
    --tm-space-xs: 0.5rem;
    --tm-space-sm: 0.75rem;
    --tm-space-md: 1rem;
    --tm-space-lg: 1.5rem;
    --tm-space-xl: 2rem;
    --tm-space-xxl: 3rem;
    
    --tm-font-size-xs: 0.75rem;
    --tm-font-size-sm: 0.875rem;
    --tm-font-size-base: 1rem;
    --tm-font-size-lg: 1.125rem;
    --tm-font-size-xl: 1.25rem;
    --tm-font-size-2xl: 1.5rem;
    --tm-font-size-3xl: 1.875rem;
    
    --tm-radius-sm: 0.375rem;
    --tm-radius-md: 0.5rem;
    --tm-radius-lg: 0.75rem;
    --tm-radius-xl: 1rem;
    --tm-radius-full: 9999px;
    
    --tm-transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Base styles */
* {
    transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6;
    color: var(--tm-text-primary);
    background: var(--tm-background);
}

/* Smooth scroll */
html {
    scroll-behavior: smooth;
}

/* Enhanced hero section */
.tm-hero {
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: var(--tm-radius-xl);
    padding: var(--tm-space-xl);
    margin-bottom: var(--tm-space-lg);
    box-shadow: var(--tm-shadow-lg);
    position: relative;
    overflow: hidden;
    animation: fadeInUp 0.6s ease-out;
}

.tm-hero::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--tm-primary), var(--tm-secondary), var(--tm-accent));
    background-size: 200% 100%;
    animation: gradientShift 3s ease infinite;
}

.tm-hero::after {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}

.tm-hero h3 {
    margin-bottom: var(--tm-space-md);
    color: var(--tm-text-on-light);
    font-size: var(--tm-font-size-2xl);
    font-weight: 700;
    letter-spacing: -0.025em;
}

.tm-hero p {
    margin-bottom: var(--tm-space-md);
    color: var(--tm-text-muted-light);
    font-size: var(--tm-font-size-base);
    line-height: 1.7;
}

.tm-hero ul,
.tm-hero li {
    color: var(--tm-text-muted-light);
}

/* Enhanced feature chips */
.tm-feature-chip {
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: var(--tm-radius-lg);
    padding: var(--tm-space-lg);
    margin-bottom: var(--tm-space-md);
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    transition: var(--tm-transition);
    position: relative;
    overflow: hidden;
    cursor: pointer;
    color: var(--tm-text-on-light);
}

.tm-feature-chip::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.1), transparent);
    transition: left 0.5s ease;
}

.tm-feature-chip:hover {
    border-color: var(--tm-primary);
    transform: translateY(-4px);
    box-shadow: var(--tm-shadow-lg), 0 0 20px rgba(59, 130, 246, 0.2);
}

.tm-feature-chip:hover::before {
    left: 100%;
}

.tm-feature-chip strong {
    display: block;
    color: var(--tm-primary);
    margin-bottom: var(--tm-space-sm);
    font-size: var(--tm-font-size-lg);
    font-weight: 600;
}

.tm-feature-chip span {
    font-size: var(--tm-font-size-sm);
    color: var(--tm-text-muted-light);
    line-height: 1.6;
}

/* Enhanced stat cards */
.tm-stat-card {
    border: 1px solid var(--tm-border);
    border-radius: var(--tm-radius-xl);
    padding: var(--tm-space-xl);
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    text-align: center;
    color: var(--tm-text-on-light);
    transition: var(--tm-transition);
    position: relative;
    overflow: hidden;
    cursor: default;
}

.tm-stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--tm-primary), var(--tm-secondary));
    transform: scaleX(0);
    transform-origin: left;
    transition: transform 0.3s ease;
}

.tm-stat-card:hover {
    transform: translateY(-4px) scale(1.02);
    box-shadow: var(--tm-shadow-xl);
    border-color: var(--tm-primary);
}

.tm-stat-card:hover::before {
    transform: scaleX(1);
}

.tm-stat-card span {
    display: block;
    font-size: var(--tm-font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--tm-text-muted-light);
    font-weight: 600;
    margin-bottom: var(--tm-space-sm);
}

.tm-stat-card strong {
    display: block;
    font-size: var(--tm-font-size-3xl);
    font-weight: 700;
    background: linear-gradient(135deg, var(--tm-primary), var(--tm-secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* Enhanced tabs */
.stTabs [role="tablist"] {
    display: inline-flex;
    gap: var(--tm-space-xs);
    padding: var(--tm-space-sm);
    margin: var(--tm-space-lg) 0 var(--tm-space-xl);
    border-radius: var(--tm-radius-full);
    border: 1px solid rgba(148, 163, 184, 0.25);
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    box-shadow: var(--tm-shadow-md);
    position: relative;
}

.stTabs [role="tab"] {
    border: none;
    border-radius: var(--tm-radius-full);
    padding: var(--tm-space-sm) var(--tm-space-xl);
    font-size: var(--tm-font-size-sm);
    font-weight: 600;
    color: var(--tm-text-muted-light);
    transition: var(--tm-transition);
    position: relative;
    overflow: hidden;
    cursor: pointer;
}

.stTabs [role="tab"]::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(135deg, var(--tm-primary), var(--tm-secondary));
    opacity: 0;
    transition: opacity 0.3s ease;
}

.stTabs [role="tab"]:hover {
    color: var(--tm-text-on-light);
    background: rgba(148, 163, 184, 0.12);
    transform: translateY(-2px);
}

.stTabs [role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, var(--tm-primary), var(--tm-secondary));
    color: white;
    box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4);
    transform: translateY(-2px) scale(1.05);
}

/* Enhanced sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--tm-surface), var(--tm-background));
    border-right: 1px solid var(--tm-border);
}

[data-testid="stSidebar"] .tm-sidebar-list {
    color: var(--tm-text-primary);
    font-size: var(--tm-font-size-sm);
    line-height: 1.6;
    padding-left: var(--tm-space-lg);
    margin-bottom: var(--tm-space-lg);
}

[data-testid="stSidebar"] .tm-sidebar-list li,
[data-testid="stSidebar"] .tm-sidebar-list li p {
    color: var(--tm-text-primary);
    margin: 0 0 var(--tm-space-xs);
}

[data-testid="stSidebar"] .tm-sidebar-card {
    border: 1px solid var(--tm-border);
    border-radius: var(--tm-radius-lg);
    background: var(--tm-surface-light);
    color: var(--tm-text-primary);
    padding: var(--tm-space-md);
    margin-bottom: var(--tm-space-md);
    box-shadow: var(--tm-shadow-md);
    transition: var(--tm-transition);
}
[data-testid="stSidebar"] .tm-sidebar-card strong {
    display: block;
    color: var(--tm-text-primary);
    font-size: var(--tm-font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--tm-space-xs);
}
[data-testid="stSidebar"] .tm-sidebar-card code {
    display: block;
    background: transparent;
    padding: 0;
    color: var(--tm-primary-light);
    font-size: var(--tm-font-size-xs);
    font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace;
    white-space: pre-wrap;
    word-break: break-word;
}

[data-testid="stSidebar"] .tm-sidebar-card:hover {
    border-color: var(--tm-primary);
    box-shadow: var(--tm-shadow-lg);
    transform: translateX(4px);
}

/* Enhanced buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--tm-primary), var(--tm-primary-dark));
    color: white;
    border: none;
    border-radius: var(--tm-radius-md);
    padding: var(--tm-space-sm) var(--tm-space-xl);
    font-weight: 600;
    font-size: var(--tm-font-size-sm);
    transition: var(--tm-transition);
    box-shadow: var(--tm-shadow-md);
    position: relative;
    overflow: hidden;
}

.stButton > button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    transition: left 0.5s ease;
}

.stButton > button:hover {
    background: linear-gradient(135deg, var(--tm-primary-hover), var(--tm-primary));
    transform: translateY(-2px);
    box-shadow: var(--tm-shadow-lg), var(--tm-shadow-glow);
}

.stButton > button:hover::before {
    left: 100%;
}

.stButton > button:active {
    transform: translateY(0);
}

/* Enhanced form elements */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: var(--tm-surface-ambient);
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: var(--tm-radius-md);
    color: var(--tm-text-on-light);
    padding: var(--tm-space-sm);
    transition: var(--tm-transition);
}

.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--tm-primary);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
    outline: none;
}

/* Enhanced expanders */
.stExpander {
    background: var(--tm-surface-ambient);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: var(--tm-radius-lg);
    margin-bottom: var(--tm-space-md);
    transition: var(--tm-transition);
}

.stExpander:hover {
    border-color: var(--tm-border-strong);
    box-shadow: var(--tm-shadow-md);
}

/* Enhanced alerts */
.stSuccess, .stError, .stWarning, .stInfo {
    border-radius: var(--tm-radius-lg);
    padding: var(--tm-space-md);
    margin: var(--tm-space-md) 0;
    border-left: 4px solid;
    animation: slideInRight 0.3s ease-out;
}

.stSuccess {
    background: var(--tm-success-bg);
    border-left-color: var(--tm-success);
    color: var(--tm-success);
}

.stError {
    background: var(--tm-error-bg);
    border-left-color: var(--tm-error);
    color: var(--tm-error);
}

.stWarning {
    background: var(--tm-warning-bg);
    border-left-color: var(--tm-warning);
    color: var(--tm-warning);
}

.stInfo {
    background: var(--tm-info-bg);
    border-left-color: var(--tm-info);
    color: var(--tm-info);
}

/* Enhanced dataframes */
[data-testid="stDataFrame"] {
    border-radius: var(--tm-radius-lg);
    overflow: hidden;
    box-shadow: var(--tm-shadow-lg);
}

/* Loading spinner enhancement */
.stSpinner > div {
    border-color: var(--tm-primary) !important;
}

/* Animations */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes slideInRight {
    from {
        opacity: 0;
        transform: translateX(-20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes gradientShift {
    0%, 100% {
        background-position: 0% 50%;
    }
    50% {
        background-position: 100% 50%;
    }
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}

/* File uploader enhancement */
[data-testid="stFileUploader"] {
    border: 2px dashed var(--tm-border);
    border-radius: var(--tm-radius-lg);
    padding: var(--tm-space-xl);
    background: var(--tm-surface-ambient);
    transition: var(--tm-transition);
}

[data-testid="stFileUploader"]:hover {
    border-color: var(--tm-primary);
    background: var(--tm-surface-ambient-alt);
}

/* Code blocks */
.stCode {
    background: var(--tm-surface-ambient) !important;
    border: 1px solid var(--tm-border) !important;
    border-radius: var(--tm-radius-lg) !important;
    box-shadow: var(--tm-shadow-md);
    color: var(--tm-text-on-light) !important;
}

/* Callout enhancement */
.tm-callout {
    border-left: 4px solid var(--tm-primary);
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    padding: var(--tm-space-lg);
    border-radius: var(--tm-radius-lg);
    margin-bottom: var(--tm-space-md);
    color: var(--tm-text-on-light);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-left-width: 4px;
    box-shadow: var(--tm-shadow-md);
    animation: fadeInUp 0.4s ease-out;
}

/* Highlight cards */
.tm-highlight-card {
    border: 1px solid var(--tm-border);
    border-radius: var(--tm-radius-xl);
    padding: var(--tm-space-xl);
    margin-bottom: var(--tm-space-lg);
    background: linear-gradient(135deg, var(--tm-surface-ambient), var(--tm-surface-ambient-alt));
    transition: var(--tm-transition);
    box-shadow: var(--tm-shadow-md);
    color: var(--tm-text-on-light);
}

.tm-highlight-card p,
.tm-highlight-card li {
    color: var(--tm-text-muted-light);
}

.tm-highlight-card:hover {
    border-color: var(--tm-border-strong);
    box-shadow: var(--tm-shadow-lg);
    transform: translateY(-2px);
}

.tm-highlight-card h4 {
    margin-bottom: var(--tm-space-md);
    color: var(--tm-primary);
    font-size: var(--tm-font-size-xl);
    font-weight: 600;
}

/* Review workflow layout */
.tm-review-card {
    background: var(--tm-surface-ambient);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: var(--tm-radius-xl);
    padding: var(--tm-space-lg);
    margin-bottom: var(--tm-space-md);
    box-shadow: var(--tm-shadow-sm);
}
.tm-review-card--compact {
    padding: var(--tm-space-md);
}
.tm-review-card--info {
    background: linear-gradient(135deg, var(--tm-surface-ambient), #ffffff);
}
.tm-review-card h4 {
    margin: 0 0 var(--tm-space-sm);
    color: var(--tm-text-on-light);
    font-size: var(--tm-font-size-lg);
    font-weight: 600;
}
.tm-review-card p {
    margin: 0 0 var(--tm-space-sm);
    color: var(--tm-text-muted-light);
    font-size: var(--tm-font-size-sm);
}
.tm-review-steps,
.tm-review-queue {
    list-style: none;
    margin: 0;
    padding: 0;
}
.tm-review-steps li,
.tm-review-queue li {
    position: relative;
    padding-left: 1.5rem;
    margin-bottom: var(--tm-space-xs);
    color: var(--tm-text-muted-light);
    font-size: var(--tm-font-size-sm);
}
.tm-review-steps li::before,
.tm-review-queue li::before {
    content: "\\2022";
    position: absolute;
    left: 0.4rem;
    color: var(--tm-primary);
    font-weight: 700;
}
.tm-review-queue li code {
    color: var(--tm-primary);
}
.tm-review-placeholder {
    color: var(--tm-text-muted-light);
    font-size: var(--tm-font-size-sm);
}
.tm-review-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--tm-space-xs);
    margin-top: var(--tm-space-sm);
}
.tm-meta-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: var(--tm-radius-full);
    background: rgba(148, 163, 184, 0.2);
    color: var(--tm-text-on-light);
    font-size: var(--tm-font-size-xs);
    font-weight: 600;
    letter-spacing: 0.02em;
}
.tm-meta-chip code {
    color: inherit;
    background: transparent;
    padding: 0;
    font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace;
    font-size: inherit;
}
.tm-severity-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: var(--tm-radius-full);
    font-size: var(--tm-font-size-xs);
    font-weight: 600;
    letter-spacing: 0.05em;
}
.tm-severity-chip--critical {
    background: rgba(239, 68, 68, 0.15);
    color: #b91c1c;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
.tm-severity-chip--high {
    background: rgba(249, 115, 22, 0.15);
    color: #9a3412;
    border: 1px solid rgba(249, 115, 22, 0.3);
}
.tm-severity-chip--medium {
    background: rgba(234, 179, 8, 0.18);
    color: #92400e;
    border: 1px solid rgba(234, 179, 8, 0.3);
}
.tm-severity-chip--low {
    background: rgba(59, 130, 246, 0.12);
    color: var(--tm-primary-dark);
    border: 1px solid rgba(59, 130, 246, 0.28);
}
.tm-severity-chip--info {
    background: rgba(20, 184, 166, 0.12);
    color: #0f766e;
    border: 1px solid rgba(13, 148, 136, 0.25);
}

/* Doc snippets */
.tm-doc-snippet {
    border: 1px solid var(--tm-border);
    border-radius: var(--tm-radius-lg);
    padding: var(--tm-space-lg);
    margin-bottom: var(--tm-space-md);
    background: var(--tm-surface-ambient);
    transition: var(--tm-transition);
    animation: fadeInUp 0.3s ease-out;
    color: var(--tm-text-on-light);
}

.tm-doc-snippet:hover {
    border-color: var(--tm-primary);
    box-shadow: var(--tm-shadow-md);
    transform: translateX(4px);
}

/* Progress bar enhancement */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--tm-primary), var(--tm-secondary)) !important;
}

/* Responsive improvements */
@media (max-width: 768px) {
    .tm-hero, .tm-feature-chip, .tm-highlight-card, .tm-stat-card {
        padding: var(--tm-space-md);
    }

    .tm-hero h3 {
        font-size: var(--tm-font-size-xl);
    }

    .tm-stat-card strong {
        font-size: var(--tm-font-size-xl);
    }
    
    .stTabs [role="tab"] {
        padding: var(--tm-space-xs) var(--tm-space-md);
        font-size: var(--tm-font-size-xs);
    }
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: var(--tm-background);
}

::-webkit-scrollbar-thumb {
    background: var(--tm-surface-lighter);
    border-radius: var(--tm-radius-md);
}

::-webkit-scrollbar-thumb:hover {
    background: var(--tm-primary);
}

/* Selection styling */
::selection {
    background: rgba(59, 130, 246, 0.3);
    color: var(--tm-text-primary);
}
</style>
"""

RESOURCE_TIPS: Dict[str, Dict[str, str]] = {
    "AWS": {
        "S3 Bucket": "Opinionated S3 bucket with encryption, TLS-only access, lifecycle defaults, and optional remote state backend.",
        "VPC Baseline": "Hub-and-spoke friendly VPC with flow logs, public/private subnets, and tagging aligned to environment stages.",
        "ALB + WAF Baseline": "Application Load Balancer secured with managed WAF, logging, and optional dedicated access log bucket.",
        "RDS Baseline": "Production-ready RDS instance with encryption, automated backups, and subnet group scaffolding.",
        "RDS Multi-Region Replica": "Cross-region managed replica pattern for disaster recovery with encrypted storage and monitoring hooks.",
        "Observability Baseline": "CloudWatch alarms, metrics filters, and SNS plumbing to keep teams alerted on drift or outage signals.",
        "ECS Fargate Service": "Managed Fargate service with least-privilege IAM roles, logging retention, and deployment guardrails.",
        "EKS Cluster": "Secure EKS control plane with OIDC provider, metrics server, and logging primitives for production clusters.",
        "EKS IRSA Service Module": "Scoped IRSA role and service account trio to plug workloads into AWS APIs with least privilege.",
    },
    "Azure": {
        "Storage Account": "Hardened blob storage with TLS, network restrictions, private endpoints, and optional Terraform backend.",
        "VNet Baseline": "Opinionated landing zone VNet with subnets, NSG flow logs, and Log Analytics integration.",
        "Key Vault": "Secure vault deployment covering soft-delete, purge protection, RBAC assignments, and diagnostics.",
        "Diagnostics Baseline": "Centralized diagnostics settings across resources, Log Analytics, and optional alerting hooks.",
        "AKS Cluster": "Private-ready AKS cluster with Azure Policy integration, node pools, and logging retention presets.",
    },
    "On‑Prem (Kubernetes)": {
        "Kubernetes Deployment": "12-factor deployment manifest with security contexts, resource guards, and optional remote state.",
        "Namespace Baseline": "Namespace scaffolding including labels, quotas, limit ranges, and network policy stubs.",
        "PodSecurity Baseline": "Cluster-wide PodSecurity policies with service account bindings for secure defaults.",
        "PodSecurity Namespace Set": "Targeted PodSecurity configurations per namespace so teams inherit the right guardrails.",
        "HPA + PDB": "Horizontal Pod Autoscaler paired with PodDisruptionBudget for resilient and scalable workloads.",
        "Argo CD Baseline": "Production-tuned Argo CD installation with optional ingress, SSO, and network hardening.",
    },
}


def _validate_generated_content(fname: str, content: str) -> Optional[str]:
    syntax_issue = _validate_hcl_syntax(content)
    if syntax_issue:
        return f"HCL parsing failed: {syntax_issue}"
    terraform_issue = _validate_with_terraform(fname, content)
    if terraform_issue:
        return terraform_issue
    return None


def _validate_hcl_syntax(content: str) -> Optional[str]:
    try:
        import hcl2  # type: ignore
    except ImportError:
        LOGGER.warning("python-hcl2 unavailable; skipping syntax validation for generated template.")
        return None
    try:
        hcl2.load(io.StringIO(content))
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("HCL parsing failed for generated template", exc_info=exc)
        return str(exc)
    return None


def _validate_with_terraform(fname: str, content: str) -> Optional[str]:
    try:
        with tempfile.TemporaryDirectory(prefix="tm-validate-") as tmpdir:
            tmp_path = Path(tmpdir) / fname
            tmp_path.write_text(content, encoding="utf-8")
            findings = run_terraform_validate([tmp_path])
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "terraform validate could not run for generated template",
            extra={"filename": fname},
            exc_info=exc,
        )
        return None
    if findings:
        first = findings[0]
        snippet = (first.get("snippet") or "").strip()
        if not snippet:
            snippet = "terraform validate reported an error. Check inputs and try again."
        if len(snippet) > 1000:
            snippet = f"{snippet[:1000]}…"
        return snippet
    return None


def _store_generation_output(key: str, fname: str, content: str) -> None:
    validation_error = _validate_generated_content(fname, content)
    if validation_error:
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}_flash", None)
        st.session_state[f"{key}_validated"] = False
        st.error(f"Terraform validation failed:\n\n{validation_error}")
        LOGGER.error(
            "Generated template failed validation",
            extra={"filename": fname, "error": validation_error},
        )
        return
    st.session_state[key] = {"fname": fname, "content": content}
    st.session_state[f"{key}_flash"] = True
    st.session_state[f"{key}_validated"] = True


def _render_generation_output(key: str, language: str = "hcl") -> None:
    result = st.session_state.get(key)
    if not result:
        return
    if st.session_state.pop(f"{key}_flash", False):
        st.success(f"Generated {result['fname']}")
    if st.session_state.get(f"{key}_validated"):
        st.caption("terraform validate passed locally for this file.")
    st.download_button(
        "Download .tf",
        data=result["content"],
        file_name=result["fname"],
        mime="text/plain",
        key=f"{key}_download",
    )
    st.code(result["content"], language=language)


def infer_azure_diag_categories(resource_id: str, fallback_log: str, resource_hint: Optional[str] = None) -> Dict[str, object]:
    rid_lower = (resource_id or "").lower()
    log_categories: List[str] = []
    resource_type = resource_hint or "generic"

    hint = (resource_hint or "").lower()
    if hint == "key_vault":
        log_categories = ["AuditEvent"]
    elif hint == "storage_account":
        log_categories = ["StorageRead", "StorageWrite", "StorageDelete"]
        resource_type = "storage_account"
    elif hint == "network_security_group":
        log_categories = ["NetworkSecurityGroupEvent", "NetworkSecurityGroupRuleCounter"]
        resource_type = "network_security_group"
    elif hint == "subnet":
        log_categories = ["VMProtectionAlerts", "VMProtectionEvents"]
        resource_type = "subnet"
    elif hint == "virtual_network":
        log_categories = ["VMProtectionAlerts", "VMProtectionEvents"]
        resource_type = "virtual_network"

    if not log_categories:
        if "microsoft.keyvault/vaults" in rid_lower:
            resource_type = "key_vault"
            log_categories = ["AuditEvent"]
        elif "microsoft.storage/storageaccounts" in rid_lower:
            resource_type = "storage_account"
            log_categories = ["StorageRead", "StorageWrite", "StorageDelete"]
        elif "microsoft.network/networksecuritygroups" in rid_lower:
            resource_type = "network_security_group"
            log_categories = ["NetworkSecurityGroupEvent", "NetworkSecurityGroupRuleCounter"]
        elif "microsoft.network/virtualnetworks" in rid_lower and "/subnets/" in rid_lower:
            resource_type = "subnet"
            log_categories = ["VMProtectionAlerts", "VMProtectionEvents"]
        elif "microsoft.network/virtualnetworks" in rid_lower:
            resource_type = "virtual_network"
            log_categories = ["VMProtectionAlerts", "VMProtectionEvents"]
        else:
            resource_type = "generic"

    if not log_categories and fallback_log:
        log_categories = [fallback_log]

    # Deduplicate while preserving order and drop empties
    seen = set()
    cleaned_logs = []
    for cat in log_categories:
        if cat and cat not in seen:
            cleaned_logs.append(cat)
            seen.add(cat)

    return {
        "resource_type": resource_type,
        "log_categories": cleaned_logs,
        "metric_categories": ["AllMetrics"],
    }

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Generate Terraform for AWS/Azure/On‑Prem (K8s), review configs, and get actionable fixes with local KB explanations.")
st.markdown(CUSTOM_PAGE_STYLE, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Quick start")
    st.markdown(
        """
        <ol class="tm-sidebar-list">
            <li>Generate a hardened baseline tailored to your provider.</li>
            <li>Upload Terraform for review or drop the generated files back in.</li>
            <li>Cross-reference findings with the knowledge base and ship with confidence.</li>
        </ol>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("### CLI shortcuts")
    st.markdown(
        """
        <div class="tm-sidebar-card">
            <strong>Scan fixtures</strong>
            <code>python -m backend.cli scan sample --out tmp/report.json</code>
        </div>
        <div class="tm-sidebar-card">
            <strong>Rebuild knowledge index</strong>
            <code>python -m backend.cli reindex</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Tip: set `OPENAI_API_KEY` (or Azure equivalents) before enabling AI assistance in the Review tab."
    )

tab1, tab2, tab3 = st.tabs(["🧰 Generate", "🔍 Review", "📚 Knowledge"])

# ------------------------------ Generate ------------------------------
with tab1:
    hero_cols = st.columns([3, 2])
    with hero_cols[0]:
        st.markdown(
            """
            <div class="tm-hero">
                <h3>Ship Terraform faster with built-in guardrails</h3>
                <p>Bootstrap secure infrastructure from curated blueprints, validate existing IaC against policy gates, and bring remediation context from your own knowledge base.</p>
                <ul>
                    <li>Hardened defaults across AWS, Azure, and on-prem Kubernetes targets.</li>
                    <li>Optional AI assist for explanations and patch prototypes.</li>
                    <li>Deterministic reporting aligned with your org severity gates.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_cols[1]:
        st.markdown(
            """
            <div class="tm-feature-chip">
                <strong>Generator wizard</strong>
                <span>Guided forms scaffold Terraform with best-practice defaults and tagging.</span>
            </div>
            <div class="tm-feature-chip">
                <strong>Risk reviewer</strong>
                <span>Upload IaC for instant diff, severity gating, and optional <code>terraform validate</code>.</span>
            </div>
            <div class="tm-feature-chip">
                <strong>Knowledge-driven fixes</strong>
                <span>Surface remediation context from your local Markdown knowledge base.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    metrics_cols = st.columns(3)
    metrics_cols[0].markdown(
        '<div class="tm-stat-card"><span>Blueprints</span><strong>18+</strong></div>',
        unsafe_allow_html=True,
    )
    metrics_cols[1].markdown(
        '<div class="tm-stat-card"><span>Policy Checks</span><strong>60+</strong></div>',
        unsafe_allow_html=True,
    )
    kb_value = f"{KNOWLEDGE_DOC_COUNT}" if KNOWLEDGE_DOC_COUNT else "Bring yours"
    metrics_cols[2].markdown(
        f'<div class="tm-stat-card"><span>Knowledge Docs</span><strong>{kb_value}</strong></div>',
        unsafe_allow_html=True,
    )

    st.subheader("Generate Terraform from a guided wizard")
    st.markdown(
        """
        <div class="tm-highlight-card">
            <h4>Blueprint checklist</h4>
            <ul>
                <li>Pick your cloud or on-prem target to load contextual fields.</li>
                <li>Override defaults interleaved with guidance snippets before generating.</li>
                <li>Download the rendered <code>.tf</code> file or feed it straight into the Review tab.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    provider = st.selectbox("Target", ["On‑Prem (Kubernetes)", "Azure", "AWS"], index=0)

    if provider == "AWS":
        resource = st.selectbox(
            "Resource",
            [
                "S3 Bucket",
                "VPC Baseline",
                "ALB + WAF Baseline",
                "RDS Baseline",
                "RDS Multi-Region Replica",
                "Observability Baseline",
                "ECS Fargate Service",
                "EKS Cluster",
                "EKS IRSA Service Module",
            ],
            index=0,
        )
        resource_tip = RESOURCE_TIPS.get(provider, {}).get(resource)
        if resource_tip:
            st.markdown(
                f'<div class="tm-callout"><strong>{resource}</strong><br>{resource_tip}</div>',
                unsafe_allow_html=True,
            )
        if resource == "S3 Bucket":
            with st.form("aws_form"):
                col1, col2 = st.columns(2)
                with col1:
                    bucket_name = st.text_input("Bucket name", value="my-team-app-bucket")
                    region = st.text_input("Region", value="us-east-1")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0)
                with col2:
                    versioning = st.checkbox("Enable versioning", value=True)
                    force_destroy = st.checkbox("Allow force_destroy (dev only)", value=False)
                    use_kms = st.checkbox("Use KMS (aws:kms)", value=False)
                    kms_key_id = st.text_input(
                        "KMS key id (optional)",
                        value="alias/aws/s3",
                        disabled=not use_kms,
                    )
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE")
                enforce_secure_transport = st.checkbox("Enforce HTTPS-only bucket policy", value=True)
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{bucket_name}-tfstate",
                        disabled=not include_backend,
                        key="aws_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/s3/{bucket_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{bucket_name.replace('-', '_')}_tf_locks",
                        disabled=not include_backend,
                        key="aws_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_s3 = st.form_submit_button("Generate .tf", type="primary")
                if submitted_s3:
                    template_path = BASE_DIR / "backend" / "generators" / "aws_s3_bucket.tf.j2"
                    t = Template(template_path.read_text())
                    rendered = t.render(
                        name="bucket",
                        bucket_name=bucket_name,
                        region=region,
                        environment=environment,
                        versioning=versioning,
                        force_destroy=force_destroy,
                        kms_key_id=(kms_key_id if use_kms else ""),
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        enforce_secure_transport=enforce_secure_transport,
                        backend=backend_context,
                    )
                    fname = f"aws_s3_{bucket_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "VPC Baseline":
            with st.form("aws_vpc_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0)
                    name_prefix = st.text_input("Name prefix (tags + resource names)", value="app")
                    vpc_cidr = st.text_input("VPC CIDR", value="10.10.0.0/16")
                with col2:
                    public_subnet_cidr = st.text_input("Public subnet CIDR", value="10.10.0.0/24")
                    private_subnet_cidr = st.text_input("Private subnet CIDR", value="10.10.1.0/24")
                az_col1, az_col2 = st.columns(2)
                with az_col1:
                    public_subnet_az = st.text_input("Public subnet AZ", value="us-east-1a")
                with az_col2:
                    private_subnet_az = st.text_input("Private subnet AZ", value="us-east-1b")
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_vpc_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_vpc_cost_center")
                flow_logs_retention = st.number_input("Flow logs retention (days)", value=90, min_value=7, max_value=365)
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_vpc_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{name_prefix}-network-tfstate",
                        disabled=not include_backend,
                        key="aws_vpc_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/networking/{name_prefix}.tfstate",
                        disabled=not include_backend,
                        key="aws_vpc_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_vpc_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{name_prefix}_network_tf_locks",
                        disabled=not include_backend,
                        key="aws_vpc_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_vpc = st.form_submit_button("Generate networking .tf", type="primary")
                if submitted_vpc:
                    template_path = BASE_DIR / "backend" / "generators" / "aws_vpc_networking.tf.j2"
                    t = Template(template_path.read_text())
                    rendered = t.render(
                        region=region,
                        environment=environment,
                        name_prefix=name_prefix,
                        vpc_cidr=vpc_cidr,
                        vpc_name="vpc",
                        private_subnet_name="subnet",
                        public_subnet_cidr=public_subnet_cidr,
                        private_subnet_cidr=private_subnet_cidr,
                        public_subnet_az=public_subnet_az,
                        private_subnet_az=private_subnet_az,
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        flow_logs_retention_days=int(flow_logs_retention),
                        backend=backend_context,
                    )
                    fname = f"aws_vpc_{name_prefix}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "ALB + WAF Baseline":
            with st.form("aws_alb_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1", key="aws_alb_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="aws_alb_env")
                    alb_actual_name = st.text_input("ALB name", value="app-alb")
                    internal = st.checkbox("Internal load balancer", value=False)
                with col2:
                    waf_actual_name = st.text_input("WAF name", value="app-alb-waf")
                    ssl_policy = st.selectbox("SSL policy", ["ELBSecurityPolicy-TLS13-1-2-2021-06", "ELBSecurityPolicy-2016-08"], index=0)
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_alb_owner")
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_alb_cost")
                subnet_ids_input = st.text_input("Subnet IDs (comma separated)", value="subnet-111, subnet-222")
                sg_ids_input = st.text_input("Security group IDs (comma separated)", value="sg-abc123")
                enable_access_logs = st.checkbox("Enable ALB access logging", value=True, help="Writes logs to S3 and enforces TLS for delivery.")
                log_bucket_name = ""
                log_bucket_prefix = ""
                create_log_bucket = False
                if enable_access_logs:
                    log_bucket_name = st.text_input("Access log bucket name", value=f"{alb_actual_name}-logs", key="aws_alb_log_bucket")
                    log_bucket_prefix = st.text_input("Access log prefix", value=f"{alb_actual_name}/alb", key="aws_alb_log_prefix")
                    create_log_bucket = st.checkbox("Create and manage log bucket", value=True, key="aws_alb_log_bucket_create")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_alb_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{alb_actual_name}-tfstate",
                        disabled=not include_backend,
                        key="aws_alb_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/alb/{alb_actual_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_alb_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_alb_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{alb_actual_name.replace('-', '_')}_alb_tf_locks",
                        disabled=not include_backend,
                        key="aws_alb_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                st.caption("Note: provide ACM certificate ARN and target group ARN when applying (variables `alb_certificate_arn`, `target_group_arn`).")
                submitted_alb = st.form_submit_button("Generate ALB + WAF .tf", type="primary")
                if submitted_alb:
                    subnet_ids_literal = "[" + ", ".join(f'"{sub.strip()}"' for sub in subnet_ids_input.split(",") if sub.strip()) + "]"
                    sg_ids_literal = "[" + ", ".join(f'"{sg.strip()}"' for sg in sg_ids_input.split(",") if sg.strip()) + "]"
                    log_bucket_resource_name = ""
                    if enable_access_logs and create_log_bucket:
                        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", log_bucket_name)
                        if not sanitized or sanitized[0].isdigit():
                            sanitized = f"logs_{sanitized}"
                        log_bucket_resource_name = sanitized.lower()
                    rendered = Template((BASE_DIR / "backend" / "generators" / "aws_alb_waf.tf.j2").read_text()).render(
                        region=region,
                        environment=environment,
                        alb_name="alb",
                        alb_actual_name=alb_actual_name,
                        waf_name="waf",
                        waf_actual_name=waf_actual_name,
                        security_group_ids_literal=sg_ids_literal,
                        subnet_ids_literal=subnet_ids_literal,
                        ssl_policy=ssl_policy,
                        internal=internal,
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        enable_access_logs=enable_access_logs,
                        create_log_bucket=create_log_bucket if enable_access_logs else False,
                        log_bucket_name=log_bucket_name,
                        log_bucket_prefix=log_bucket_prefix,
                        log_bucket_resource_name=log_bucket_resource_name,
                        backend=backend_context,
                    )
                    fname = f"aws_alb_{alb_actual_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "RDS Baseline":
            with st.form("aws_rds_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1", key="aws_rds_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="aws_rds_env")
                    db_identifier = st.text_input("DB identifier", value="prod-app-db")
                    db_name = st.text_input("Database name", value="appdb")
                    engine = st.selectbox("Engine", ["postgres", "mysql", "mariadb"], index=0)
                with col2:
                    engine_version = st.text_input("Engine version", value="14.10")
                    instance_class = st.text_input("Instance class", value="db.m6i.large")
                    allocated_storage = st.number_input("Allocated storage (GiB)", value=100, min_value=20, step=10)
                    max_allocated_storage = st.number_input("Max allocated storage (GiB)", value=200, min_value=allocated_storage, step=10)
                    multi_az = st.checkbox("Enable Multi-AZ", value=True)
                subnet_ids_input = st.text_input("DB subnet IDs (comma separated)", value="subnet-111, subnet-222")
                sg_ids_input = st.text_input("Security group IDs (comma separated)", value="sg-abc123")
                logs_exports = st.text_input("CloudWatch logs exports (comma separated)", value="postgresql, upgrade")
                backup_retention = st.number_input("Backup retention (days)", value=7, min_value=1, max_value=35)
                preferred_backup_window = st.text_input("Preferred backup window", value="03:00-04:00")
                preferred_maintenance_window = st.text_input("Preferred maintenance window", value="sun:05:00-sun:06:00")
                kms_key_id = st.text_input("KMS key ARN (optional)", value="")
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_rds_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_rds_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_rds_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{db_identifier}-tfstate",
                        disabled=not include_backend,
                        key="aws_rds_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/rds/{db_identifier}.tfstate",
                        disabled=not include_backend,
                        key="aws_rds_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_rds_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{db_identifier.replace('-', '_')}_rds_tf_locks",
                        disabled=not include_backend,
                        key="aws_rds_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_rds = st.form_submit_button("Generate RDS .tf", type="primary")
                if submitted_rds:
                    subnet_ids_literal = "[" + ", ".join(f'"{sub.strip()}"' for sub in subnet_ids_input.split(",") if sub.strip()) + "]"
                    sg_ids_literal = "[" + ", ".join(f'"{sg.strip()}"' for sg in sg_ids_input.split(",") if sg.strip()) + "]"
                    logs_exports_literal = "[" + ", ".join(f'"{log.strip()}"' for log in logs_exports.split(",") if log.strip()) + "]" if logs_exports.strip() else "[]"
                    rendered = Template((BASE_DIR / "backend" / "generators" / "aws_rds_baseline.tf.j2").read_text()).render(
                        region=region,
                        environment=environment,
                        db_identifier=db_identifier,
                        db_name=db_name,
                        engine=engine,
                        engine_version=engine_version,
                        instance_class=instance_class,
                        allocated_storage=int(allocated_storage),
                        max_allocated_storage=int(max_allocated_storage),
                        multi_az=multi_az,
                        subnet_group_name=f"{db_identifier}-subnets",
                        subnet_ids_literal=subnet_ids_literal,
                        security_group_ids_literal=sg_ids_literal,
                        logs_exports_literal=logs_exports_literal,
                        backup_retention=int(backup_retention),
                        preferred_backup_window=preferred_backup_window,
                        preferred_maintenance_window=preferred_maintenance_window,
                        kms_key_id=kms_key_id.strip(),
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        backend=backend_context,
                    )
                    fname = f"aws_rds_{db_identifier.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "RDS Multi-Region Replica":
            with st.form("aws_rds_multi_region_form"):
                col1, col2 = st.columns(2)
                with col1:
                    primary_region = st.text_input("Primary region", value="us-east-1", key="aws_rds_multi_primary_region")
                    secondary_region = st.text_input("Secondary region", value="us-west-2", key="aws_rds_multi_secondary_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="aws_rds_multi_env")
                    primary_db_identifier = st.text_input("Primary DB identifier", value="prod-app-db", key="aws_rds_multi_primary_identifier")
                    replica_db_identifier = st.text_input("Replica DB identifier", value="prod-app-db-usw2", key="aws_rds_multi_replica_identifier")
                    db_name = st.text_input("Database name", value="appdb", key="aws_rds_multi_db_name")
                    engine = st.selectbox("Engine", ["postgres", "mysql", "mariadb"], index=0, key="aws_rds_multi_engine")
                    engine_version = st.text_input("Engine version", value="14.10", key="aws_rds_multi_engine_version")
                    instance_class = st.text_input("Primary instance class", value="db.m6i.large", key="aws_rds_multi_instance_class")
                with col2:
                    replica_instance_class = st.text_input("Replica instance class", value="db.m6i.large", key="aws_rds_multi_replica_class")
                    allocated_storage = st.number_input("Allocated storage (GiB)", value=100, min_value=20, step=10, key="aws_rds_multi_allocated_storage")
                    max_allocated_storage = st.number_input(
                        "Max allocated storage (GiB)",
                        value=200,
                        min_value=int(allocated_storage),
                        step=10,
                        key="aws_rds_multi_max_storage",
                    )
                    multi_az = st.checkbox("Enable Multi-AZ (primary)", value=True, key="aws_rds_multi_multi_az")
                    logs_exports = st.text_input("CloudWatch logs exports (comma separated)", value="postgresql, upgrade", key="aws_rds_multi_logs")
                    primary_kms_key_id = st.text_input("Primary KMS key ARN (optional)", value="", key="aws_rds_multi_primary_kms")
                    replica_kms_key_id = st.text_input("Replica KMS key ARN (optional)", value="", key="aws_rds_multi_replica_kms")
                primary_subnets = st.text_input("Primary subnet IDs (comma separated)", value="subnet-111, subnet-222", key="aws_rds_multi_primary_subnets")
                replica_subnets = st.text_input("Replica subnet IDs (comma separated)", value="subnet-aaa, subnet-bbb", key="aws_rds_multi_replica_subnets")
                primary_sg_ids = st.text_input("Primary security group IDs (comma separated)", value="sg-primary", key="aws_rds_multi_primary_sgs")
                replica_sg_ids = st.text_input("Replica security group IDs (comma separated)", value="sg-replica", key="aws_rds_multi_replica_sgs")
                backup_retention = st.number_input("Backup retention (days)", value=7, min_value=1, max_value=35, key="aws_rds_multi_backup_retention")
                preferred_backup_window = st.text_input("Preferred backup window", value="03:00-05:00", key="aws_rds_multi_backup_window")
                preferred_maintenance_window = st.text_input("Preferred maintenance window", value="sun:05:00-sun:06:00", key="aws_rds_multi_maintenance_window")
                backup_vault_name = st.text_input("Primary backup vault name", value="prod-app-backup", key="aws_rds_multi_backup_vault")
                replica_backup_vault_name = st.text_input("Replica backup vault name", value="prod-app-backup-usw2", key="aws_rds_multi_replica_vault")
                backup_plan_name = st.text_input("Backup plan name", value="prod-app-backup-plan", key="aws_rds_multi_plan")
                backup_rule_name = st.text_input("Backup rule name", value="daily-backup", key="aws_rds_multi_rule_name")
                backup_selection_name = st.text_input("Backup selection name", value="rds-primary-selection", key="aws_rds_multi_selection")
                backup_cron = st.text_input("Backup schedule cron", value="cron(0 7 * * ? *)", key="aws_rds_multi_cron")
                cold_storage_after = st.number_input("Cold storage after (days)", value=30, min_value=0, key="aws_rds_multi_cold_storage")
                delete_after = st.number_input("Delete backups after (days)", value=120, min_value=30, key="aws_rds_multi_delete_after")
                backup_kms_key_arn = st.text_input("Primary backup vault KMS key ARN", value="arn:aws:kms:us-east-1:123456789012:key/example", key="aws_rds_multi_backup_kms")
                replica_backup_kms_key_arn = st.text_input("Replica backup vault KMS key ARN", value="arn:aws:kms:us-west-2:123456789012:key/example", key="aws_rds_multi_replica_backup_kms")
                backup_iam_role_arn = st.text_input("Backup IAM role ARN", value="arn:aws:iam::123456789012:role/service-role/AWSBackupDefaultServiceRole", key="aws_rds_multi_backup_role")
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_rds_multi_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_rds_multi_cost_center")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_rds_multi_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{primary_db_identifier}-tfstate",
                        disabled=not include_backend,
                        key="aws_rds_multi_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/rds/{primary_db_identifier}-multi-region.tfstate",
                        disabled=not include_backend,
                        key="aws_rds_multi_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=primary_region,
                        disabled=not include_backend,
                        key="aws_rds_multi_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{primary_db_identifier.replace('-', '_')}_multi_region_tf_locks",
                        disabled=not include_backend,
                        key="aws_rds_multi_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_rds_multi = st.form_submit_button("Generate multi-region RDS .tf", type="primary")
                if submitted_rds_multi:
                    validation_errors = []
                    required_pairs = [
                        ("Primary backup vault name", backup_vault_name),
                        ("Replica backup vault name", replica_backup_vault_name),
                        ("Backup plan name", backup_plan_name),
                        ("Backup rule name", backup_rule_name),
                        ("Backup selection name", backup_selection_name),
                        ("Backup schedule cron", backup_cron),
                        ("Backup IAM role ARN", backup_iam_role_arn),
                        ("Primary backup vault KMS key ARN", backup_kms_key_arn),
                        ("Replica backup vault KMS key ARN", replica_backup_kms_key_arn),
                    ]
                    for label, value in required_pairs:
                        if not value.strip():
                            validation_errors.append(f"Provide a value for **{label}** to configure cross-region backups.")
                    if validation_errors:
                        st.error("\n".join(validation_errors))
                    else:
                        primary_subnet_literal = "[" + ", ".join(f'"{sub.strip()}"' for sub in primary_subnets.split(",") if sub.strip()) + "]"
                        replica_subnet_literal = "[" + ", ".join(f'"{sub.strip()}"' for sub in replica_subnets.split(",") if sub.strip()) + "]"
                        primary_sg_literal = "[" + ", ".join(f'"{sg.strip()}"' for sg in primary_sg_ids.split(",") if sg.strip()) + "]"
                        replica_sg_literal = "[" + ", ".join(f'"{sg.strip()}"' for sg in replica_sg_ids.split(",") if sg.strip()) + "]"
                        logs_exports_literal = "[" + ", ".join(f'"{log.strip()}"' for log in logs_exports.split(",") if log.strip()) + "]" if logs_exports.strip() else "[]"
                        template_path = BASE_DIR / "backend" / "generators" / "aws_rds_multi_region.tf.j2"
                        sanitize = lambda value: re.sub(r"[^0-9A-Za-z_]", "_", value)
                        primary_subnet_group_name = f"{primary_db_identifier}-primary-subnets"
                        replica_subnet_group_name = f"{replica_db_identifier}-subnets"
                        rendered = Template(template_path.read_text()).render(
                            primary_region=primary_region,
                            secondary_region=secondary_region,
                            environment=environment,
                            primary_db_identifier=primary_db_identifier,
                            replica_db_identifier=replica_db_identifier,
                            primary_resource_name=sanitize(primary_db_identifier),
                            replica_resource_name=sanitize(replica_db_identifier),
                            db_name=db_name,
                            engine=engine,
                            engine_version=engine_version,
                            instance_class=instance_class,
                            replica_instance_class=replica_instance_class,
                            allocated_storage=int(allocated_storage),
                            max_allocated_storage=int(max_allocated_storage),
                            multi_az=multi_az,
                            primary_subnet_group_name=primary_subnet_group_name,
                            replica_subnet_group_name=replica_subnet_group_name,
                            primary_subnet_group_resource_name=sanitize(primary_subnet_group_name),
                            replica_subnet_group_resource_name=sanitize(replica_subnet_group_name),
                            primary_subnet_ids_literal=primary_subnet_literal,
                            replica_subnet_ids_literal=replica_subnet_literal,
                            primary_security_group_ids_literal=primary_sg_literal,
                            replica_security_group_ids_literal=replica_sg_literal,
                            logs_exports_literal=logs_exports_literal,
                            backup_retention=int(backup_retention),
                            preferred_backup_window=preferred_backup_window,
                            preferred_maintenance_window=preferred_maintenance_window,
                            primary_kms_key_id=primary_kms_key_id.strip(),
                            replica_kms_key_id=replica_kms_key_id.strip(),
                            owner_tag=owner_tag,
                            cost_center_tag=cost_center_tag,
                            backup_vault_name=backup_vault_name,
                            replica_backup_vault_name=replica_backup_vault_name,
                            backup_vault_resource_name=sanitize(backup_vault_name),
                            replica_backup_vault_resource_name=sanitize(replica_backup_vault_name),
                            backup_plan_name=backup_plan_name,
                            backup_plan_resource_name=sanitize(backup_plan_name),
                            backup_rule_name=backup_rule_name,
                            backup_selection_name=backup_selection_name,
                            backup_selection_resource_name=sanitize(backup_selection_name),
                            backup_cron=backup_cron,
                            cold_storage_after=int(cold_storage_after),
                            delete_after=int(delete_after),
                            backup_kms_key_arn=backup_kms_key_arn.strip(),
                            replica_backup_kms_key_arn=replica_backup_kms_key_arn.strip(),
                            backup_iam_role_arn=backup_iam_role_arn.strip(),
                            backend=backend_context,
                        )
                        fname = f"aws_rds_multi_region_{primary_db_identifier.replace('-', '_')}.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
        elif resource == "Observability Baseline":
            with st.form("aws_observability_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1", key="aws_obs_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="aws_obs_env")
                    trail_name = st.text_input("CloudTrail name", value="org-trail")
                    cloudtrail_bucket = st.text_input("CloudTrail bucket name", value="org-trail-logs")
                with col2:
                    config_recorder_name = st.text_input("Config recorder name", value="default", key="aws_obs_recorder")
                    config_role_name = st.text_input("Config IAM role name", value="aws-config-role", key="aws_obs_role")
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_obs_owner")
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_obs_cost")
                kms_key_id = st.text_input("KMS key ARN (optional)", value="", key="aws_obs_kms")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_obs_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{trail_name}-tfstate",
                        disabled=not include_backend,
                        key="aws_obs_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/observability/{trail_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_obs_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_obs_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{trail_name.replace('-', '_')}_obs_tf_locks",
                        disabled=not include_backend,
                        key="aws_obs_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_obs = st.form_submit_button("Generate observability .tf", type="primary")
                if submitted_obs:
                    template_path = BASE_DIR / "backend" / "generators" / "aws_observability_baseline.tf.j2"
                    rendered = Template(template_path.read_text()).render(
                        region=region,
                        environment=environment,
                        trail_name=trail_name,
                        trail_bucket_name=trail_name.replace("-", "_"),
                        cloudtrail_bucket=cloudtrail_bucket,
                        kms_key_id=kms_key_id.strip(),
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        config_recorder_name=config_recorder_name,
                        config_role_name=config_role_name,
                        backend=backend_context,
                    )
                    fname = f"aws_observability_{trail_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "ECS Fargate Service":
            with st.form("aws_ecs_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1", key="aws_ecs_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="aws_ecs_env")
                    cluster_actual_name = st.text_input("ECS cluster name", value="app-ecs-cluster")
                    service_actual_name = st.text_input("Service name", value="app-web-service")
                    desired_count = st.number_input("Desired task count", min_value=1, value=2, step=1)
                    cpu = st.selectbox("Task CPU", ["256", "512", "1024", "2048"], index=1)
                with col2:
                    memory = st.selectbox("Task memory (MiB)", ["512", "1024", "2048", "4096", "8192"], index=2)
                    container_name = st.text_input("Container name", value="web")
                    container_image = st.text_input("Container image", value="public.ecr.aws/nginx/nginx:stable")
                    container_port = st.number_input("Container port", min_value=1, max_value=65535, value=8080, step=1)
                    platform_version = st.text_input("Fargate platform version", value="1.4.0")
                    enable_execute_command = st.checkbox("Enable ECS Exec", value=True, help="Allow secure debugging via AWS Systems Manager Session Manager.")
                subnet_ids_input = st.text_input("Private subnet IDs (comma separated)", value="subnet-abc123, subnet-def456")
                sg_ids_input = st.text_input("Security group IDs (comma separated)", value="sg-abc123")
                health_check_grace_period = st.number_input("Health check grace period (seconds)", min_value=0, value=60, step=5)
                circuit_breaker_enabled = st.checkbox("Enable deployment circuit breaker with rollback", value=True)
                read_only_root_fs = st.checkbox("Enforce read-only root filesystem", value=True)
                log_retention_days = st.number_input("Log retention (days)", min_value=1, max_value=3653, value=30, step=1)
                log_kms_key_id = st.text_input("CloudWatch Logs KMS key ARN (optional)", value="", help="Leave blank to use the CloudWatch Logs managed KMS key.")
                ssm_arns_input = st.text_area(
                    "SSM parameter ARNs to allow task access (one per line)",
                    value="",
                    help="Grant least-privilege read access to specific Parameter Store paths.",
                )
                env_input = st.text_area(
                    "Environment variables (KEY=VALUE per line)",
                    value="ENVIRONMENT=prod\nLOG_LEVEL=info",
                )
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_ecs_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_ecs_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_ecs_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{service_actual_name}-tfstate",
                        disabled=not include_backend,
                        key="aws_ecs_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/ecs/{service_actual_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_ecs_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_ecs_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{service_actual_name.replace('-', '_')}_ecs_tf_locks",
                        disabled=not include_backend,
                        key="aws_ecs_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted_ecs = st.form_submit_button("Generate ECS Fargate .tf", type="primary")
                if submitted_ecs:
                    subnet_ids = [s.strip() for s in subnet_ids_input.split(",") if s.strip()]
                    sg_ids = [s.strip() for s in sg_ids_input.split(",") if s.strip()]
                    if not subnet_ids:
                        st.error("Provide at least one subnet ID for the service.")
                    elif not sg_ids:
                        st.error("Provide at least one security group ID for the service.")
                    else:
                        def _sanitize(value: str, fallback: str) -> str:
                            sanitized = re.sub(r"[^A-Za-z0-9_]", "_", value or fallback)
                            sanitized = re.sub(r"_+", "_", sanitized).strip("_")
                            if not sanitized:
                                sanitized = fallback
                            if sanitized[0].isdigit():
                                sanitized = f"r_{sanitized}"
                            return sanitized.lower()

                        cluster_resource_name = _sanitize(cluster_actual_name, "ecs_cluster")
                        service_resource_name = _sanitize(service_actual_name, "ecs_service")
                        execution_role_resource_name = _sanitize(f"{service_actual_name}_exec", "ecs_exec_role")
                        execution_role_actual_name = f"{service_actual_name}-exec-role"
                        task_role_resource_name = _sanitize(f"{service_actual_name}_task_role", "ecs_task_role")
                        task_role_actual_name = f"{service_actual_name}-task-role"
                        task_definition_resource_name = _sanitize(f"{service_actual_name}_taskdef", "ecs_task_definition")
                        task_family = f"{service_actual_name}-task"
                        log_group_resource_name = _sanitize(f"{service_actual_name}_logs", "ecs_logs")

                        subnet_ids_literal = "[" + ", ".join(f'"{s}"' for s in subnet_ids) + "]"
                        security_group_ids_literal = "[" + ", ".join(f'"{s}"' for s in sg_ids) + "]"

                        ssm_parameter_arns = [line.strip() for line in ssm_arns_input.splitlines() if line.strip()]
                        ssm_parameter_arns_literal = "[" + ", ".join(f'"{arn}"' for arn in ssm_parameter_arns) + "]" if ssm_parameter_arns else "[]"
                        has_ssm_parameters = bool(ssm_parameter_arns)

                        env_pairs = []
                        for line in env_input.splitlines():
                            if "=" in line:
                                key, value = line.split("=", 1)
                                env_pairs.append({"name": key.strip(), "value": value.strip()})

                        container_def = {
                            "name": container_name,
                            "image": container_image,
                            "essential": True,
                            "portMappings": [
                                {
                                    "containerPort": int(container_port),
                                    "hostPort": int(container_port),
                                    "protocol": "tcp"
                                }
                            ],
                            "logConfiguration": {
                                "logDriver": "awslogs",
                                "options": {
                                    "awslogs-group": f"/aws/ecs/{cluster_actual_name}/{service_actual_name}",
                                    "awslogs-region": region,
                                    "awslogs-stream-prefix": container_name
                                }
                            }
                        }
                        if env_pairs:
                            container_def["environment"] = env_pairs
                        if read_only_root_fs:
                            container_def["readonlyRootFilesystem"] = True

                        container_definitions_json = json.dumps([container_def], indent=2)

                        template_path = BASE_DIR / "backend" / "generators" / "aws_ecs_fargate_service.tf.j2"
                        rendered = Template(template_path.read_text()).render(
                            region=region,
                            environment=environment,
                            cluster_resource_name=cluster_resource_name,
                            cluster_actual_name=cluster_actual_name,
                            service_resource_name=service_resource_name,
                            service_actual_name=service_actual_name,
                            execution_role_resource_name=execution_role_resource_name,
                            execution_role_actual_name=execution_role_actual_name,
                            task_role_resource_name=task_role_resource_name,
                            task_role_actual_name=task_role_actual_name,
                            task_definition_resource_name=task_definition_resource_name,
                            task_family=task_family,
                            cpu=cpu,
                            memory=memory,
                            desired_count=int(desired_count),
                            platform_version=platform_version,
                            enable_execute_command=enable_execute_command,
                            circuit_breaker_enabled=circuit_breaker_enabled,
                            health_check_grace_period=int(health_check_grace_period) if health_check_grace_period > 0 else None,
                            subnet_ids_literal=subnet_ids_literal,
                            security_group_ids_literal=security_group_ids_literal,
                            log_group_resource_name=log_group_resource_name,
                            log_retention_days=int(log_retention_days),
                            log_kms_key_id=log_kms_key_id.strip(),
                            ssm_parameter_arns_literal=ssm_parameter_arns_literal,
                            has_ssm_parameters=has_ssm_parameters,
                            container_definitions_json=container_definitions_json,
                            owner_tag=owner_tag,
                            cost_center_tag=cost_center_tag,
                            backend=backend_context,
                        )
                        fname = f"aws_ecs_{service_resource_name}.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
        elif resource == "EKS Cluster":
            with st.form("aws_eks_form"):
                col1, col2 = st.columns(2)
                with col1:
                    cluster_name = st.text_input("Cluster name", value="app-eks")
                    region = st.text_input("Region", value="us-east-1", key="aws_eks_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="aws_eks_env")
                    kubernetes_version = st.text_input("Kubernetes version", value="1.29")
                with col2:
                    vpc_id = st.text_input("Existing VPC ID", value="vpc-abc123")
                    private_subnet_ids_input = st.text_area("Private subnet IDs (comma separated)", value="subnet-abc123, subnet-def456")
                    allow_public_api = st.checkbox("Allow public API access (locked to CIDRs)", value=False)
                    public_cidrs_input = st.text_input("Public access CIDRs", value="203.0.113.0/32", disabled=not allow_public_api)
                col3, col4 = st.columns(2)
                with col3:
                    node_instance_types_input = st.text_input("Node instance types", value="m6i.large")
                    node_ami_type = st.selectbox("AMI type", ["AL2_x86_64", "AL2_x86_64_GPU", "AL2_ARM_64"], index=0)
                    capacity_type = st.selectbox("Capacity type", ["ON_DEMAND", "SPOT"], index=0)
                    kms_key_arn = st.text_input("KMS key ARN (for secrets encryption)", value="")
                with col4:
                    node_desired_size = st.number_input("Desired nodes", value=3, min_value=1, step=1)
                    node_min_size = st.number_input("Min nodes", value=3, min_value=1, step=1)
                    node_max_size = st.number_input("Max nodes", value=6, min_value=1, step=1)
                    node_disk_size = st.number_input("Node disk size (GiB)", value=50, min_value=20, step=5)
                    enforce_imdsv2 = st.checkbox("Require IMDSv2 on nodes", value=True, help="Creates a launch template with metadata tokens required.")
                    if enforce_imdsv2:
                        st.caption("Disk size remains provider default when using the launch template; adjust via the template if needed.")
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_eks_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_eks_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_eks_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{cluster_name}-tfstate",
                        disabled=not include_backend,
                        key="aws_eks_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/eks/{cluster_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_eks_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_eks_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{cluster_name.replace('-', '_')}_eks_tf_locks",
                        disabled=not include_backend,
                        key="aws_eks_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted = st.form_submit_button("Generate EKS .tf", type="primary")
                if submitted:
                    private_subnet_ids = [s.strip() for s in private_subnet_ids_input.split(",") if s.strip()]
                    if not private_subnet_ids:
                        st.error("Provide at least one private subnet ID.")
                    else:
                        private_subnet_ids_literal = "[" + ", ".join(f'"{s}"' for s in private_subnet_ids) + "]"
                        instance_types = [s.strip() for s in node_instance_types_input.split(",") if s.strip()]
                        instance_types_literal = "[" + ", ".join(f'"{s}"' for s in instance_types) + "]"
                        public_access_cidrs_literal = "[]"
                        if allow_public_api:
                            public_cidrs = [s.strip() for s in public_cidrs_input.split(",") if s.strip()]
                            public_access_cidrs_literal = "[" + ", ".join(f'"{s}"' for s in public_cidrs) + "]"
                        t = Template((BASE_DIR / "backend" / "generators" / "aws_eks_cluster.tf.j2").read_text())
                        rendered = t.render(
                            region=region,
                            environment=environment,
                            cluster_name=cluster_name,
                            kubernetes_version=kubernetes_version,
                            vpc_id=vpc_id,
                            private_subnet_ids_literal=private_subnet_ids_literal,
                            allow_public_api=allow_public_api,
                            public_access_cidrs_literal=public_access_cidrs_literal,
                            kms_key_arn=kms_key_arn.strip(),
                            node_ami_type=node_ami_type,
                            node_disk_size=int(node_disk_size),
                            capacity_type=capacity_type,
                            node_desired_size=int(node_desired_size),
                            node_min_size=int(node_min_size),
                            node_max_size=int(node_max_size),
                            instance_types_literal=instance_types_literal,
                            owner_tag=owner_tag,
                            cost_center_tag=cost_center_tag,
                            enforce_imdsv2=enforce_imdsv2,
                            backend=backend_context,
                        )
                        fname = f"aws_eks_{cluster_name.replace('-', '_')}.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
        elif resource == "EKS IRSA Service Module":
            with st.form("aws_eks_irsa_form"):
                col1, col2 = st.columns(2)
                with col1:
                    region = st.text_input("Region", value="us-east-1", key="aws_irsa_region")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="aws_irsa_env")
                    cluster_name = st.text_input("Existing EKS cluster name", value="app-eks")
                    namespace = st.text_input("Kubernetes namespace", value="app")
                    service_account_name = st.text_input("Service account name", value="app-sa")
                with col2:
                    oidc_provider_arn = st.text_input(
                        "OIDC provider ARN",
                        value="arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/EXAMPLE",
                    )
                    psa_enforce_level = st.selectbox("PodSecurity enforce level", ["restricted", "baseline", "privileged"], index=0)
                    psa_warn_level = st.selectbox("PodSecurity warn level", ["baseline", "restricted", "privileged"], index=1)
                    psa_audit_level = st.selectbox("PodSecurity audit level", ["restricted", "baseline", "privileged"], index=0)
                    create_namespace = st.checkbox("Manage namespace in Terraform", value=True)
                policy_actions_input = st.text_area(
                    "IAM policy actions (one per line)",
                    value="s3:GetObject\ns3:ListBucket",
                )
                policy_resources_input = st.text_area(
                    "IAM policy resource ARNs (one per line)",
                    value="arn:aws:s3:::example-bucket\narn:aws:s3:::example-bucket/*",
                )
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="aws_irsa_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="aws_irsa_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox('Emit terraform backend "s3"', value=False, key="aws_irsa_backend_toggle")
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{cluster_name}-irsa-tfstate",
                        disabled=not include_backend,
                        key="aws_irsa_backend_bucket",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/eks/{namespace}/{service_account_name}.tfstate",
                        disabled=not include_backend,
                        key="aws_irsa_backend_key",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value=region,
                        disabled=not include_backend,
                        key="aws_irsa_backend_region",
                    )
                    backend_table = st.text_input(
                        "DynamoDB lock table",
                        value=f"{namespace}_{service_account_name}_irsa_tf_locks",
                        disabled=not include_backend,
                        key="aws_irsa_backend_table",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "bucket": backend_bucket,
                        "key": backend_key,
                        "region": backend_region,
                        "dynamodb_table": backend_table,
                    }
                submitted = st.form_submit_button("Generate EKS IRSA module .tf", type="primary")
                if submitted:
                    policy_actions = [line.strip() for line in policy_actions_input.splitlines() if line.strip()]
                    policy_resources = [line.strip() for line in policy_resources_input.splitlines() if line.strip()]
                    validation_error = None
                    if not policy_actions:
                        validation_error = "Provide at least one IAM action."
                    elif not policy_resources:
                        validation_error = "Provide at least one IAM resource ARN."
                    elif "oidc-provider/" not in oidc_provider_arn:
                        validation_error = "OIDC provider ARN must include 'oidc-provider/'."

                    if validation_error:
                        st.error(validation_error)
                    else:
                        def _sanitize(value: str, fallback: str) -> str:
                            sanitized = re.sub(r"[^A-Za-z0-9_]", "_", value or fallback)
                            sanitized = re.sub(r"_+", "_", sanitized).strip("_")
                            if not sanitized:
                                sanitized = fallback
                            if sanitized[0].isdigit():
                                sanitized = f"r_{sanitized}"
                            return sanitized.lower()

                        cluster_data_resource_name = _sanitize(f"{cluster_name}_cluster_data", "eks_cluster")
                        namespace_resource_name = _sanitize(namespace, "eks_ns")
                        service_account_resource_name = _sanitize(f"{namespace}_{service_account_name}", "eks_sa")
                        iam_role_resource_name = _sanitize(f"{service_account_name}_irsa_role", "eks_irsa_role")
                        iam_role_actual_name = f"{service_account_name}-irsa-role"
                        iam_role_policy_resource_name = _sanitize(f"{service_account_name}_irsa_policy", "eks_irsa_policy")
                        iam_policy_name = f"{service_account_name}-access"

                        oidc_provider_host = oidc_provider_arn.split("oidc-provider/", 1)[1]

                        policy_document = {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Sid": "ApplicationAccess",
                                    "Effect": "Allow",
                                    "Action": policy_actions,
                                    "Resource": policy_resources,
                                }
                            ],
                        }
                        policy_document_json = json.dumps(policy_document, indent=2)

                        template_path = BASE_DIR / "backend" / "generators" / "aws_eks_irsa_service.tf.j2"
                        rendered = Template(template_path.read_text()).render(
                            region=region,
                            environment=environment,
                            cluster_name=cluster_name,
                            cluster_data_resource_name=cluster_data_resource_name,
                            namespace=namespace,
                            namespace_resource_name=namespace_resource_name,
                            service_account_name=service_account_name,
                            service_account_resource_name=service_account_resource_name,
                            oidc_provider_arn=oidc_provider_arn,
                            oidc_provider_host=oidc_provider_host,
                            create_namespace=create_namespace,
                            iam_role_resource_name=iam_role_resource_name,
                            iam_role_actual_name=iam_role_actual_name,
                            iam_role_policy_resource_name=iam_role_policy_resource_name,
                            iam_policy_name=iam_policy_name,
                            policy_document_json=policy_document_json,
                            psa_enforce_level=psa_enforce_level,
                            psa_warn_level=psa_warn_level,
                            psa_audit_level=psa_audit_level,
                            owner_tag=owner_tag,
                            cost_center_tag=cost_center_tag,
                            backend=backend_context,
                        )
                        fname = f"aws_eks_irsa_{namespace_resource_name}_{service_account_resource_name}.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
    elif provider == "Azure":
        resource = st.selectbox("Resource", ["Storage Account", "VNet Baseline", "Key Vault", "Diagnostics Baseline", "AKS Cluster"], index=0)
        resource_tip = RESOURCE_TIPS.get(provider, {}).get(resource)
        if resource_tip:
            st.markdown(
                f'<div class="tm-callout"><strong>{resource}</strong><br>{resource_tip}</div>',
                unsafe_allow_html=True,
            )
        if resource == "Storage Account":
            with st.form("azure_form"):
                col1, col2 = st.columns(2)
                with col1:
                    rg_actual_name = st.text_input("Resource Group name", value="rg-app")
                    sa_actual_name = st.text_input("Storage Account name (globally unique)", value="stapp1234567890")
                    location = st.text_input("Location", value="eastus")
                with col2:
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0)
                    replication = st.selectbox("Replication", ["LRS", "GRS", "RAGRS", "ZRS"], index=0)
                    versioning = st.checkbox("Enable blob versioning", value=True)
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    azure_owner_tag = st.text_input("Tag: Owner", value="platform-team", key="azure_owner_tag")
                with tag_col2:
                    azure_cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="azure_cost_center_tag")
                restrict_network = st.checkbox(
                    "Restrict network access to specific IP ranges",
                    value=(environment == "prod"),
                    key="azure_storage_restrict_network",
                )
                allowed_ips_input = st.text_input(
                    "Allowed IPv4 ranges (comma separated)",
                    value="10.0.0.0/24" if restrict_network else "",
                    disabled=not restrict_network,
                    key="azure_storage_allowed_ips",
                )
                with st.expander("Private endpoint (optional)", expanded=False):
                    enable_private_endpoint = st.checkbox(
                        "Create private endpoint",
                        value=False,
                        key="azure_storage_private_endpoint_toggle",
                    )
                    private_endpoint_name = st.text_input(
                        "Private endpoint name",
                        value=f"{sa_actual_name}-pe",
                        disabled=not enable_private_endpoint,
                        key="azure_storage_private_endpoint_name",
                    )
                    private_endpoint_connection = st.text_input(
                        "Private service connection name",
                        value=f"{sa_actual_name}-blob",
                        disabled=not enable_private_endpoint,
                        key="azure_storage_private_endpoint_connection",
                    )
                    private_endpoint_subnet_id = st.text_input(
                        "Private endpoint subnet ID",
                        value="/subscriptions/.../subnets/storage-private-endpoint",
                        disabled=not enable_private_endpoint,
                        key="azure_storage_private_endpoint_subnet",
                    )
                    private_dns_zone_id = st.text_input(
                        "Private DNS zone ID (optional)",
                        value="/subscriptions/.../resourceGroups/rg-network/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
                        disabled=not enable_private_endpoint,
                        key="azure_storage_private_dns_zone_id",
                    )
                    private_dns_zone_group_name = st.text_input(
                        "Private DNS zone group name",
                        value=f"{sa_actual_name}-blob-zone",
                        disabled=not enable_private_endpoint or not private_dns_zone_id.strip(),
                        key="azure_storage_private_dns_zone_group",
                    )
                with st.expander("Remote state backend (optional)", expanded=False):
                    azure_include_backend = st.checkbox(
                        'Emit terraform backend "azurerm"', value=False, key="azure_backend_toggle"
                    )
                    azure_backend_rg = st.text_input(
                        "State resource group",
                        value=f"{rg_actual_name}-tfstate",
                        disabled=not azure_include_backend,
                        key="azure_backend_rg",
                    )
                    azure_backend_account = st.text_input(
                        "State storage account",
                        value=f"{sa_actual_name}tfstate",
                        disabled=not azure_include_backend,
                        key="azure_backend_account",
                    )
                    azure_backend_container = st.text_input(
                        "State container",
                        value="tfstate",
                        disabled=not azure_include_backend,
                        key="azure_backend_container",
                    )
                    azure_backend_key = st.text_input(
                        "State blob key",
                        value=f"{environment}/terraform.tfstate",
                        disabled=not azure_include_backend,
                        key="azure_backend_key",
                    )
                azure_backend_context = None
                if azure_include_backend:
                    azure_backend_context = {
                        "resource_group": azure_backend_rg,
                        "storage_account": azure_backend_account,
                        "container": azure_backend_container,
                        "key": azure_backend_key,
                    }
                submitted = st.form_submit_button("Generate .tf", type="primary")
                if submitted:
                    ip_list = [ip.strip() for ip in allowed_ips_input.split(",") if ip.strip()]
                    ip_rules_literal = "[" + ", ".join(f'"{ip}"' for ip in ip_list) + "]" if restrict_network else "[]"
                    sanitize = lambda value: re.sub(r"[^0-9A-Za-z_]", "_", value)
                    private_endpoint_context = None
                    if enable_private_endpoint:
                        dns_group_source = private_dns_zone_group_name or f"{sa_actual_name}-blob-zone"
                        private_endpoint_context = {
                            "resource_name": sanitize(private_endpoint_name),
                            "name": private_endpoint_name,
                            "connection_name": private_endpoint_connection,
                            "subnet_id": private_endpoint_subnet_id.strip(),
                            "private_dns_zone_id": private_dns_zone_id.strip(),
                            "dns_zone_group_name": sanitize(dns_group_source),
                        }
                    t = Template((BASE_DIR / "backend" / "generators" / "azure_storage_account.tf.j2").read_text())
                    rendered = t.render(
                        rg_name="rg",
                        rg_actual_name=rg_actual_name,
                        sa_name="sa",
                        sa_actual_name=sa_actual_name,
                        location=location,
                        environment=environment,
                        replication=replication,
                        versioning=versioning,
                        owner_tag=azure_owner_tag,
                        cost_center_tag=azure_cost_center_tag,
                        restrict_network=restrict_network,
                        ip_rules_literal=ip_rules_literal,
                        private_endpoint=private_endpoint_context,
                        backend=azure_backend_context,
                    )
                    fname = f"azure_storage_{sa_actual_name}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "VNet Baseline":
            with st.form("azure_vnet_form"):
                col1, col2 = st.columns(2)
                with col1:
                    rg_actual_name = st.text_input("Resource Group name", value="rg-app-network")
                    location = st.text_input("Location", value="eastus")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="azure_vnet_env")
                with col2:
                    name_prefix = st.text_input("Name prefix", value="appnet")
                    address_space = st.text_input("VNet address space", value="10.20.0.0/16")
                subnet_col1, subnet_col2 = st.columns(2)
                with subnet_col1:
                    workload_cidr = st.text_input("Workload subnet CIDR", value="10.20.1.0/24")
                with subnet_col2:
                    bastion_cidr = st.text_input("Management/Bastion subnet CIDR", value="10.20.10.0/27")
                allowed_management_cidr = st.text_input("Allowed management CIDR (SSH)", value="10.0.0.0/24")
                log_analytics_retention = st.number_input("Log Analytics retention days", value=30, min_value=7, max_value=730)
                flow_log_retention = st.number_input("NSG flow log retention days", value=90, min_value=7, max_value=365)
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    azure_owner_tag = st.text_input("Tag: Owner", value="platform-team", key="azure_vnet_owner")
                with tag_col2:
                    azure_cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="azure_vnet_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    azure_include_backend = st.checkbox(
                        'Emit terraform backend "azurerm"', value=False, key="azure_vnet_backend_toggle"
                    )
                    azure_backend_rg = st.text_input(
                        "State resource group",
                        value=f"{rg_actual_name}-tfstate",
                        disabled=not azure_include_backend,
                        key="azure_vnet_backend_rg",
                    )
                    azure_backend_account = st.text_input(
                        "State storage account",
                        value=f"{name_prefix}tfstate",
                        disabled=not azure_include_backend,
                        key="azure_vnet_backend_account",
                    )
                    azure_backend_container = st.text_input(
                        "State container",
                        value="tfstate",
                        disabled=not azure_include_backend,
                        key="azure_vnet_backend_container",
                    )
                    azure_backend_key = st.text_input(
                        "State blob key",
                        value=f"{environment}/network/{name_prefix}.tfstate",
                        disabled=not azure_include_backend,
                        key="azure_vnet_backend_key",
                    )
                azure_backend_context = None
                if azure_include_backend:
                    azure_backend_context = {
                        "resource_group": azure_backend_rg,
                        "storage_account": azure_backend_account,
                        "container": azure_backend_container,
                        "key": azure_backend_key,
                    }
                submitted = st.form_submit_button("Generate networking .tf", type="primary")
                if submitted:
                    t = Template((BASE_DIR / "backend" / "generators" / "azure_vnet_baseline.tf.j2").read_text())
                    rendered = t.render(
                        rg_name="rg",
                        rg_actual_name=rg_actual_name,
                        location=location,
                        environment=environment,
                        name_prefix=name_prefix,
                        address_space=address_space,
                        workload_subnet_cidr=workload_cidr,
                        bastion_subnet_cidr=bastion_cidr,
                        allowed_management_cidr=allowed_management_cidr,
                        log_analytics_retention_days=int(log_analytics_retention),
                        flow_log_retention_days=int(flow_log_retention),
                        owner_tag=azure_owner_tag,
                        cost_center_tag=azure_cost_center_tag,
                        backend=azure_backend_context,
                    )
                    fname = f"azure_vnet_{name_prefix}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "Key Vault":
            with st.form("azure_kv_form"):
                col1, col2 = st.columns(2)
                with col1:
                    rg_actual_name = st.text_input("Resource Group name", value="rg-keyvault")
                    location = st.text_input("Location", value="eastus2")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="azure_kv_env")
                    kv_actual_name = st.text_input("Key Vault name", value="kv-secure")
                with col2:
                    tenant_id = st.text_input("Tenant ID (GUID)", value="00000000-0000-0000-0000-000000000000")
                    vnet_id = st.text_input("Virtual Network ID", value="/subscriptions/.../virtualNetworks/vnet-secure")
                    subnet_id = st.text_input("Private endpoint subnet ID", value="/subscriptions/.../subnets/kv-endpoint")
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="azure_kv_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="azure_kv_cost")
                soft_delete_retention_days = st.number_input("Soft delete retention (days)", value=90, min_value=7, max_value=730)
                restrict_network = st.checkbox("Restrict network access (deny by default)", value=True, key="azure_kv_restrict")
                allowed_ips_input = st.text_input(
                    "Allowed IP ranges (comma separated)",
                    value="10.0.0.0/24",
                    disabled=not restrict_network,
                    key="azure_kv_ip_rules",
                )
                with st.expander("Remote state backend (optional)", expanded=False):
                    azure_include_backend = st.checkbox(
                        'Emit terraform backend "azurerm"', value=False, key="azure_kv_backend_toggle"
                    )
                    azure_backend_rg = st.text_input(
                        "State resource group",
                        value=f"{rg_actual_name}-tfstate",
                        disabled=not azure_include_backend,
                        key="azure_kv_backend_rg",
                    )
                    azure_backend_account = st.text_input(
                        "State storage account",
                        value=f"{kv_actual_name}tfstate",
                        disabled=not azure_include_backend,
                        key="azure_kv_backend_account",
                    )
                    azure_backend_container = st.text_input(
                        "State container",
                        value="tfstate",
                        disabled=not azure_include_backend,
                        key="azure_kv_backend_container",
                    )
                    azure_backend_key = st.text_input(
                        "State blob key",
                        value=f"{environment}/keyvault/{kv_actual_name}.tfstate",
                        disabled=not azure_include_backend,
                        key="azure_kv_backend_key",
                    )
                azure_backend_context = None
                if azure_include_backend:
                    azure_backend_context = {
                        "resource_group": azure_backend_rg,
                        "storage_account": azure_backend_account,
                        "container": azure_backend_container,
                        "key": azure_backend_key,
                    }
                submitted = st.form_submit_button("Generate Key Vault .tf", type="primary")
                if submitted:
                    ip_rules_literal = "[" + ", ".join(f'"{ip.strip()}"' for ip in allowed_ips_input.split(",") if ip.strip()) + "]" if restrict_network else "[]"
                    template = Template((BASE_DIR / "backend" / "generators" / "azure_key_vault.tf.j2").read_text())
                    rendered = template.render(
                        rg_name="rg",
                        rg_actual_name=rg_actual_name,
                        location=location,
                        environment=environment,
                        kv_name="kv",
                        kv_actual_name=kv_actual_name,
                        tenant_id=tenant_id,
                        soft_delete_retention_days=int(soft_delete_retention_days),
                        ip_rules_literal=ip_rules_literal,
                        vnet_id=vnet_id,
                        subnet_id=subnet_id,
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        backend=azure_backend_context,
                    )
                    fname = f"azure_keyvault_{kv_actual_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "Diagnostics Baseline":
            with st.form("azure_diag_form"):
                col1, col2 = st.columns(2)
                with col1:
                    rg_actual_name = st.text_input("Resource Group name", value="rg-diag")
                    location = st.text_input("Location", value="eastus")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="azure_diag_env")
                    law_actual_name = st.text_input("Log Analytics workspace name", value="law-diag")
                with col2:
                    log_retention_days = st.number_input("Log retention (days)", value=30, min_value=7, max_value=730)
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="azure_diag_owner")
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="azure_diag_cost")
                    diagnostic_prefix = st.text_input("Diagnostic setting name prefix", value="diag", key="azure_diag_prefix")
                resource_ids_input = st.text_area(
                    "Target resource IDs (one per line)",
                    value="",
                    placeholder="/subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/kv-secure",
                )
                default_log_category = st.text_input("Default log category", value="AuditEvent")
                create_storage_account = st.checkbox("Create storage account for archived logs", value=False)
                storage_actual_name = ""
                if create_storage_account:
                    storage_actual_name = st.text_input("Storage account name", value="logstorage123456", key="azure_diag_storage")
                st.markdown("**Optional auto-target helpers**")
                subscription_text = st.text_input(
                    "Subscription ID",
                    value="00000000-0000-0000-0000-000000000000",
                    help="Used when constructing resource IDs for NSGs, VNets, and existing assets.",
                )
                vnet_name_input = st.text_input(
                    "Virtual Network name (optional)",
                    value="",
                    help="Attach diagnostics to this VNet and any subnets listed below.",
                )
                subnet_names_input = st.text_input(
                    "Subnet names (comma separated)",
                    value="",
                    help="Requires the Virtual Network name.",
                )
                nsg_names_input = st.text_input(
                    "Network Security Groups (comma separated)",
                    value="",
                    help="Attach diagnostics to each NSG in this resource group.",
                )
                existing_storage_accounts_input = st.text_input(
                    "Existing storage accounts (comma separated)",
                    value="",
                    help="Attach diagnostics to existing storage accounts in this resource group.",
                )
                include_created_storage = False
                if create_storage_account:
                    include_created_storage = st.checkbox(
                        "Attach diagnostics to storage account created by this template",
                        value=True,
                        help="Adds a diagnostic setting for the generated storage account.",
                    )
                health_alert_enabled = st.checkbox(
                    "Create Log Analytics ingestion health alert",
                    value=True,
                    help="Adds a metric alert when workspace search availability drops below the defined threshold.",
                )
                health_alert_name = st.text_input(
                    "Health alert name",
                    value=f"{law_actual_name}-ingestion-alert",
                    disabled=not health_alert_enabled,
                )
                health_alert_description = st.text_area(
                    "Health alert description",
                    value="Alert when Log Analytics workspace query availability drops below 99% over 5 minutes.",
                    disabled=not health_alert_enabled,
                )
                health_alert_severity = st.selectbox(
                    "Alert severity (1 = critical)",
                    options=[1, 2, 3, 4],
                    index=1,
                    disabled=not health_alert_enabled,
                    key="azure_diag_health_severity",
                )
                health_alert_threshold = st.number_input(
                    "Availability threshold (%)",
                    value=99,
                    min_value=0,
                    max_value=100,
                    step=1,
                    disabled=not health_alert_enabled,
                    key="azure_diag_health_threshold",
                )
                health_alert_action_groups_input = st.text_input(
                    "Action group IDs (comma separated)",
                    value="/subscriptions/.../resourceGroups/rg-notify/providers/Microsoft.Insights/actionGroups/notify-secops",
                    disabled=not health_alert_enabled,
                )
                with st.expander("Remote state backend (optional)", expanded=False):
                    azure_include_backend = st.checkbox(
                        'Emit terraform backend "azurerm"', value=False, key="azure_diag_backend_toggle"
                    )
                    azure_backend_rg = st.text_input(
                        "State resource group",
                        value=f"{rg_actual_name}-tfstate",
                        disabled=not azure_include_backend,
                        key="azure_diag_backend_rg",
                    )
                    azure_backend_account = st.text_input(
                        "State storage account",
                        value=f"{law_actual_name}tfstate",
                        disabled=not azure_include_backend,
                        key="azure_diag_backend_account",
                    )
                    azure_backend_container = st.text_input(
                        "State container",
                        value="tfstate",
                        disabled=not azure_include_backend,
                        key="azure_diag_backend_container",
                    )
                    azure_backend_key = st.text_input(
                        "State blob key",
                        value=f"{environment}/diagnostics/{law_actual_name}.tfstate",
                        disabled=not azure_include_backend,
                        key="azure_diag_backend_key",
                    )
                azure_backend_context = None
                if azure_include_backend:
                    azure_backend_context = {
                        "resource_group": azure_backend_rg,
                        "storage_account": azure_backend_account,
                        "container": azure_backend_container,
                        "key": azure_backend_key,
                    }
                submitted = st.form_submit_button("Generate diagnostics .tf", type="primary")
                if submitted:
                    targets: List[Dict[str, object]] = []
                    preview_rows: List[Dict[str, str]] = []
                    existing_keys = set()
                    slug_tracker = set()
                    auto_warnings: List[str] = []

                    subscription_path = subscription_text.strip()
                    if subscription_path and not subscription_path.lower().startswith("/subscriptions/"):
                        subscription_path = f"/subscriptions/{subscription_path}"

                    def make_slug(raw: str) -> str:
                        base = re.sub(r"[^A-Za-z0-9_]", "_", raw) or "resource"
                        base = base.strip("_") or "resource"
                        candidate = base
                        counter = 1
                        while candidate in slug_tracker:
                            counter += 1
                            candidate = f"{base}_{counter}"
                        slug_tracker.add(candidate)
                        return candidate

                    def append_target(
                        slug_base: str,
                        resource_id_value: str,
                        id_is_literal: bool,
                        resource_hint: Optional[str] = None,
                        preview_id: Optional[str] = None,
                    ) -> None:
                        key = (resource_id_value, id_is_literal)
                        if key in existing_keys:
                            return
                        diag_meta = infer_azure_diag_categories(
                            preview_id or resource_id_value,
                            default_log_category,
                            resource_hint=resource_hint,
                        )
                        slug = make_slug(slug_base or "diag")
                        target_entry = {
                            "name": f"diag_{slug}",
                            "id": resource_id_value,
                            "id_is_literal": id_is_literal,
                            "index": len(targets) + 1,
                            "log_categories": diag_meta["log_categories"],
                            "metric_categories": diag_meta["metric_categories"],
                        }
                        targets.append(target_entry)
                        existing_keys.add(key)
                        preview_rows.append(
                            {
                                "Resource ID": preview_id or resource_id_value,
                                "Detected Type": diag_meta["resource_type"],
                                "Log Categories": ", ".join(diag_meta["log_categories"]) if diag_meta["log_categories"] else "—",
                                "Metric Categories": ", ".join(diag_meta["metric_categories"]) if diag_meta["metric_categories"] else "—",
                            }
                        )

                    for idx, line in enumerate(resource_ids_input.splitlines(), start=1):
                        rid = line.strip()
                        if not rid:
                            continue
                        slug_base = rid.split("/")[-1] or f"resource_{idx}"
                        append_target(slug_base, rid, False)

                    if create_storage_account and include_created_storage:
                        storage_expr = f"azurerm_storage_account.{storage_name}.id"
                        preview_id = (
                            f"{subscription_path}/resourceGroups/{rg_actual_name}/providers/Microsoft.Storage/storageAccounts/{storage_actual_name}"
                            if subscription_path
                            else storage_expr
                        )
                        append_target(
                            f"{storage_actual_name}_storage",
                            storage_expr,
                            True,
                            resource_hint="storage_account",
                            preview_id=preview_id,
                        )

                    if existing_storage_accounts_input.strip():
                        if not subscription_path:
                            auto_warnings.append("Subscription ID is required to attach diagnostics to existing storage accounts.")
                        else:
                            for name in [n.strip() for n in existing_storage_accounts_input.split(",") if n.strip()]:
                                resource_id = f"{subscription_path}/resourceGroups/{rg_actual_name}/providers/Microsoft.Storage/storageAccounts/{name}"
                                append_target(f"{name}_storage", resource_id, False, resource_hint="storage_account")

                    if vnet_name_input.strip():
                        if not subscription_path:
                            auto_warnings.append("Subscription ID is required to attach diagnostics to the virtual network.")
                        else:
                            vnet_name_clean = vnet_name_input.strip()
                            vnet_id = f"{subscription_path}/resourceGroups/{rg_actual_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name_clean}"
                            append_target(f"{vnet_name_clean}_vnet", vnet_id, False, resource_hint="virtual_network")
                            if subnet_names_input.strip():
                                for subnet in [s.strip() for s in subnet_names_input.split(",") if s.strip()]:
                                    subnet_id = f"{vnet_id}/subnets/{subnet}"
                                    append_target(f"{subnet}_subnet", subnet_id, False, resource_hint="subnet")
                    elif subnet_names_input.strip():
                        auto_warnings.append("Provide the Virtual Network name to attach diagnostics to the listed subnets.")

                    if nsg_names_input.strip():
                        if not subscription_path:
                            auto_warnings.append("Subscription ID is required to attach diagnostics to NSGs.")
                        else:
                            for nsg in [s.strip() for s in nsg_names_input.split(",") if s.strip()]:
                                nsg_id = f"{subscription_path}/resourceGroups/{rg_actual_name}/providers/Microsoft.Network/networkSecurityGroups/{nsg}"
                                append_target(f"{nsg}_nsg", nsg_id, False, resource_hint="network_security_group")

                    if not targets:
                        st.error("Enter at least one target resource ID or enable an auto-target option.")
                    else:
                        if preview_rows:
                            st.markdown("**Diagnostic targets**")
                            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)
                        empty_logs = [t for t in targets if not t["log_categories"]]
                        if empty_logs:
                            st.warning("Some targets lack recommended log categories; supply a default category or adjust inputs.")
                        health_alert_context = None
                        if health_alert_enabled:
                            action_group_ids = [ag.strip() for ag in health_alert_action_groups_input.split(",") if ag.strip()]
                            if not action_group_ids:
                                auto_warnings.append("Supply at least one action group ID to activate the health alert.")
                            else:
                                alert_name = health_alert_name.strip() or f"{law_actual_name}-ingestion-alert"
                                health_alert_context = {
                                    "resource_name": make_slug(alert_name),
                                    "name": alert_name,
                                    "description": health_alert_description.strip() or "Log Analytics ingestion availability alert.",
                                    "severity": int(health_alert_severity),
                                    "threshold": float(health_alert_threshold),
                                    "frequency": "PT5M",
                                    "window_size": "PT5M",
                                    "aggregation": "Average",
                                    "metric_name": "SearchServiceAvailability",
                                    "action_group_ids": action_group_ids,
                                }
                        if auto_warnings:
                            st.warning("\n".join(auto_warnings))
                        rendered = Template((BASE_DIR / "backend" / "generators" / "azure_diagnostics_baseline.tf.j2").read_text()).render(
                            rg_name="rg",
                            rg_actual_name=rg_actual_name,
                            location=location,
                            environment=environment,
                            law_name="law",
                            law_actual_name=law_actual_name,
                            log_retention_days=int(log_retention_days),
                            diagnostic_prefix=diagnostic_prefix,
                            targets=targets,
                            create_storage_account=create_storage_account,
                            storage_name="logstorage",
                            storage_actual_name=storage_actual_name,
                            health_alert=health_alert_context,
                            owner_tag=owner_tag,
                            cost_center_tag=cost_center_tag,
                            backend=azure_backend_context,
                        )
                        fname = f"azure_diagnostics_{law_actual_name.replace('-', '_')}.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
        else:
            with st.form("azure_aks_form"):
                col1, col2 = st.columns(2)
                with col1:
                    rg_actual_name = st.text_input("Resource Group name", value="rg-aks")
                    location = st.text_input("Location", value="eastus2")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="azure_aks_env")
                    cluster_name = st.text_input("Cluster name", value="aks-secure")
                with col2:
                    kubernetes_version = st.text_input("Kubernetes version", value="1.29.2")
                    dns_prefix = st.text_input("DNS prefix", value="akssecure")
                    node_pool_name = st.text_input("Node pool name", value="nodepool1")
                    node_vm_size = st.text_input("Node VM size", value="Standard_D4s_v5")
                subnet_col1, subnet_col2 = st.columns(2)
                with subnet_col1:
                    node_subnet_id = st.text_input("Node subnet ID", value="/subscriptions/.../subnets/aks-nodes")
                    private_cluster = st.checkbox("Private cluster", value=True)
                    enable_azure_policy = st.checkbox("Enable Azure Policy add-on", value=True)
                with subnet_col2:
                    authorized_ips_input = st.text_input("Authorized IP ranges", value="10.0.0.0/24", disabled=private_cluster)
                    service_cidr = st.text_input("Service CIDR", value="10.2.0.0/16")
                    dns_service_ip = st.text_input("DNS service IP", value="10.2.0.10")
                    docker_bridge_cidr = st.text_input("Docker bridge CIDR", value="172.17.0.1/16")
                node_scaling_col1, node_scaling_col2 = st.columns(2)
                with node_scaling_col1:
                    node_min_count = st.number_input("Node min count", value=3, min_value=1, step=1)
                    node_desired_count = st.number_input("Node desired count", value=3, min_value=1, step=1)
                with node_scaling_col2:
                    node_max_count = st.number_input("Node max count", value=6, min_value=1, step=1)
                    max_pods = st.number_input("Max pods per node", value=110, min_value=30, step=10)
                log_analytics_retention = st.number_input("Log Analytics retention (days)", value=30, min_value=7, max_value=730)
                tag_col1, tag_col2 = st.columns(2)
                with tag_col1:
                    owner_tag = st.text_input("Tag: Owner", value="platform-team", key="azure_aks_owner")
                with tag_col2:
                    cost_center_tag = st.text_input("Tag: CostCenter", value="ENG-SRE", key="azure_aks_cost")
                with st.expander("Remote state backend (optional)", expanded=False):
                    azure_include_backend = st.checkbox(
                        'Emit terraform backend "azurerm"', value=False, key="azure_aks_backend_toggle"
                    )
                    azure_backend_rg = st.text_input(
                        "State resource group",
                        value=f"{rg_actual_name}-tfstate",
                        disabled=not azure_include_backend,
                        key="azure_aks_backend_rg",
                    )
                    azure_backend_account = st.text_input(
                        "State storage account",
                        value=f"{cluster_name}tfstate",
                        disabled=not azure_include_backend,
                        key="azure_aks_backend_account",
                    )
                    azure_backend_container = st.text_input(
                        "State container",
                        value="tfstate",
                        disabled=not azure_include_backend,
                        key="azure_aks_backend_container",
                    )
                    azure_backend_key = st.text_input(
                        "State blob key",
                        value=f"{environment}/aks/{cluster_name}.tfstate",
                        disabled=not azure_include_backend,
                        key="azure_aks_backend_key",
                    )
                azure_backend_context = None
                if azure_include_backend:
                    azure_backend_context = {
                        "resource_group": azure_backend_rg,
                        "storage_account": azure_backend_account,
                        "container": azure_backend_container,
                        "key": azure_backend_key,
                    }
                submitted = st.form_submit_button("Generate AKS .tf", type="primary")
                if submitted:
                    authorized_ips = []
                    if not private_cluster:
                        authorized_ips = [s.strip() for s in authorized_ips_input.split(",") if s.strip()]
                    authorized_ip_literal = "[" + ", ".join(f'"{ip}"' for ip in authorized_ips) + "]"
                    t = Template((BASE_DIR / "backend" / "generators" / "azure_aks_cluster.tf.j2").read_text())
                    rendered = t.render(
                        rg_name="rg",
                        rg_actual_name=rg_actual_name,
                        location=location,
                        environment=environment,
                        cluster_name=cluster_name,
                        kubernetes_version=kubernetes_version,
                        dns_prefix=dns_prefix,
                        node_pool_name=node_pool_name,
                        node_vm_size=node_vm_size,
                        node_subnet_id=node_subnet_id,
                        private_cluster=private_cluster,
                        enable_azure_policy=enable_azure_policy,
                        authorized_ip_ranges_literal=authorized_ip_literal,
                        node_min_count=int(node_min_count),
                        node_desired_count=int(node_desired_count),
                        node_max_count=int(node_max_count),
                        max_pods=int(max_pods),
                        service_cidr=service_cidr,
                        dns_service_ip=dns_service_ip,
                        docker_bridge_cidr=docker_bridge_cidr,
                        log_analytics_retention_days=int(log_analytics_retention),
                        owner_tag=owner_tag,
                        cost_center_tag=cost_center_tag,
                        backend=azure_backend_context,
                    )
                    fname = f"azure_aks_{cluster_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)

    else:  # On‑Prem (Kubernetes)
        resource = st.selectbox(
            "Resource",
            [
                "Kubernetes Deployment",
                "Namespace Baseline",
                "PodSecurity Baseline",
                "PodSecurity Namespace Set",
                "HPA + PDB",
                "Argo CD Baseline",
            ],
            index=0,
        )
        resource_tip = RESOURCE_TIPS.get(provider, {}).get(resource)
        if resource_tip:
            st.markdown(
                f'<div class="tm-callout"><strong>{resource}</strong><br>{resource_tip}</div>',
                unsafe_allow_html=True,
            )
        if resource == "Kubernetes Deployment":
            with st.form("k8s_form"):
                col1, col2 = st.columns(2)
                with col1:
                    namespace_actual = st.text_input("Namespace", value="apps")
                    k8s_environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0)
                    app_actual = st.text_input("App name", value="my-app")
                    image = st.text_input("Container image", value="nginx:1.25.3")
                    container_port = st.number_input("Container port", value=80, step=1)
                with col2:
                    replicas = st.number_input("Replicas", value=2, step=1)
                    non_root = st.checkbox("Enforce run_as_non_root + read_only_root_fs", value=True)
                    enforce_seccomp = st.checkbox("Enforce RuntimeDefault seccomp profile", value=True)
                    enforce_apparmor = st.checkbox("Annotate pods with runtime/default AppArmor", value=True)
                    set_limits = st.checkbox("Set resources limits/requests", value=True)
                    cpu_limit = st.text_input("CPU limit", value="500m")
                    mem_limit = st.text_input("Memory limit", value="256Mi")
                    cpu_request = st.text_input("CPU request", value="250m")
                    mem_request = st.text_input("Memory request", value="128Mi")
                label_col1, label_col2 = st.columns(2)
                with label_col1:
                    k8s_team_label = st.text_input("Label: team", value="platform", key="k8s_team_label")
                with label_col2:
                    k8s_tier_label = st.text_input("Label: tier", value="backend", key="k8s_tier_label")
                with st.expander("Remote state backend (optional)", expanded=False):
                    k8s_include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_backend_toggle",
                    )
                    k8s_backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not k8s_include_backend,
                        key="k8s_backend_endpoint",
                    )
                    k8s_backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{namespace_actual}-tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_backend_bucket",
                    )
                    k8s_backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not k8s_include_backend,
                        key="k8s_backend_region",
                    )
                    k8s_backend_key = st.text_input(
                        "State object key",
                        value=f"{namespace_actual}/{app_actual}.tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_backend_key",
                    )
                k8s_backend_context = None
                if k8s_include_backend:
                    k8s_backend_context = {
                        "endpoint": k8s_backend_endpoint,
                        "bucket": k8s_backend_bucket,
                        "region": k8s_backend_region,
                        "key": k8s_backend_key,
                    }
                submitted = st.form_submit_button("Generate .tf", type="primary")
                if submitted:
                    t = Template((BASE_DIR / "backend" / "generators" / "k8s_deployment.tf.j2").read_text())
                    rendered = t.render(
                        namespace_name="ns",
                        namespace_actual=namespace_actual,
                        app_name="deploy",
                        app_actual=app_actual,
                        image=image,
                        container_port=int(container_port),
                        replicas=int(replicas),
                        non_root=non_root,
                        set_limits=set_limits,
                        cpu_limit=cpu_limit,
                        mem_limit=mem_limit,
                        cpu_request=cpu_request,
                        mem_request=mem_request,
                        environment=k8s_environment,
                        team_label=k8s_team_label,
                        tier_label=k8s_tier_label,
                        enforce_seccomp=enforce_seccomp,
                        enforce_apparmor=enforce_apparmor,
                        backend=k8s_backend_context,
                    )
                    fname = f"k8s_{app_actual.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "Namespace Baseline":
            with st.form("k8s_namespace_form"):
                namespace_actual = st.text_input("Namespace", value="apps-baseline")
                k8s_environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="k8s_ns_env")
                k8s_team_label = st.text_input("Label: team", value="platform", key="k8s_ns_team")
                quota_pods = st.text_input("Quota: pods", value="50")
                quota_limits_cpu = st.text_input("Quota: limits.cpu", value="40")
                quota_limits_memory = st.text_input("Quota: limits.memory", value="160Gi")
                quota_requests_cpu = st.text_input("Quota: requests.cpu", value="20")
                quota_requests_memory = st.text_input("Quota: requests.memory", value="80Gi")
                limit_max_cpu = st.text_input("LimitRange max cpu", value="4")
                limit_max_memory = st.text_input("LimitRange max memory", value="8Gi")
                limit_min_cpu = st.text_input("LimitRange min cpu", value="100m")
                limit_min_memory = st.text_input("LimitRange min memory", value="128Mi")
                limit_default_cpu = st.text_input("LimitRange default cpu", value="500m")
                limit_default_memory = st.text_input("LimitRange default memory", value="512Mi")
                limit_default_request_cpu = st.text_input("LimitRange default request cpu", value="250m")
                limit_default_request_memory = st.text_input("LimitRange default request memory", value="256Mi")
                with st.expander("Remote state backend (optional)", expanded=False):
                    k8s_include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_ns_backend_toggle",
                    )
                    k8s_backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not k8s_include_backend,
                        key="k8s_ns_backend_endpoint",
                    )
                    k8s_backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{namespace_actual}-tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_ns_backend_bucket",
                    )
                    k8s_backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not k8s_include_backend,
                        key="k8s_ns_backend_region",
                    )
                    k8s_backend_key = st.text_input(
                        "State object key",
                        value=f"{namespace_actual}/baseline.tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_ns_backend_key",
                    )
                k8s_backend_context = None
                if k8s_include_backend:
                    k8s_backend_context = {
                        "endpoint": k8s_backend_endpoint,
                        "bucket": k8s_backend_bucket,
                        "region": k8s_backend_region,
                        "key": k8s_backend_key,
                    }
                submitted = st.form_submit_button("Generate namespace .tf", type="primary")
                if submitted:
                    t = Template((BASE_DIR / "backend" / "generators" / "k8s_namespace_baseline.tf.j2").read_text())
                    rendered = t.render(
                        namespace_name="ns",
                        namespace_actual=namespace_actual,
                        environment=k8s_environment,
                        team_label=k8s_team_label,
                        quota_pods=quota_pods,
                        quota_limits_cpu=quota_limits_cpu,
                        quota_limits_memory=quota_limits_memory,
                        quota_requests_cpu=quota_requests_cpu,
                        quota_requests_memory=quota_requests_memory,
                        limit_max_cpu=limit_max_cpu,
                        limit_max_memory=limit_max_memory,
                        limit_min_cpu=limit_min_cpu,
                        limit_min_memory=limit_min_memory,
                        limit_default_cpu=limit_default_cpu,
                        limit_default_memory=limit_default_memory,
                        limit_default_request_cpu=limit_default_request_cpu,
                        limit_default_request_memory=limit_default_request_memory,
                        backend=k8s_backend_context,
                    )
                    fname = f"k8s_namespace_{namespace_actual.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "PodSecurity Namespace Set":
            with st.form("k8s_psa_namespace_form"):
                namespace_lines = st.text_area(
                    "Namespaces (one per line, optional team override like namespace,team)",
                    value="apps\nplatform",
                    help="Format: namespace or namespace,team for team-specific labels.",
                )
                col_env, col_team = st.columns(2)
                with col_env:
                    psa_environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="k8s_psa_env")
                    psa_version = st.text_input("PSA version", value="latest", help="Use 'latest' to follow cluster defaults.")
                with col_team:
                    psa_team_label = st.text_input("Label: team", value="platform", key="k8s_psa_team")
                    enforce_level = st.selectbox("Enforce level", ["baseline", "restricted"], index=1)
                col_warn, col_audit = st.columns(2)
                with col_warn:
                    warn_level = st.selectbox("Warn level", ["baseline", "restricted", "privileged"], index=0)
                with col_audit:
                    audit_level = st.selectbox("Audit level", ["baseline", "restricted", "privileged"], index=0)
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_psa_backend_toggle",
                    )
                    backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not include_backend,
                        key="k8s_psa_backend_endpoint",
                    )
                    backend_bucket = st.text_input(
                        "State bucket",
                        value="psa-namespaces-tfstate",
                        disabled=not include_backend,
                        key="k8s_psa_backend_bucket",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not include_backend,
                        key="k8s_psa_backend_region",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value="security/podsecurity-namespaces.tfstate",
                        disabled=not include_backend,
                        key="k8s_psa_backend_key",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "endpoint": backend_endpoint,
                        "bucket": backend_bucket,
                        "region": backend_region,
                        "key": backend_key,
                    }
                submitted = st.form_submit_button("Generate PodSecurity namespace set .tf", type="primary")
                if submitted:
                    namespaces = []
                    seen_names = set()
                    for line in namespace_lines.splitlines():
                        entry = line.strip()
                        if not entry:
                            continue
                        parts = [piece.strip() for piece in entry.split(",") if piece.strip()]
                        name = parts[0]
                        if name in seen_names:
                            continue
                        seen_names.add(name)
                        team_override = parts[1] if len(parts) > 1 else ""
                        resolved_team = team_override or psa_team_label
                        resource_name = re.sub(r"[^A-Za-z0-9_]", "_", name)
                        resource_name = resource_name.strip("_") or "namespace"
                        original = resource_name
                        counter = 1
                        while any(ns["resource_name"] == resource_name for ns in namespaces):
                            counter += 1
                            resource_name = f"{original}_{counter}"
                        namespaces.append({
                            "resource_name": resource_name,
                            "actual_name": name,
                            "team_label": resolved_team,
                        })
                    if not namespaces:
                        st.error("Provide at least one namespace name.")
                    else:
                        rendered = Template((BASE_DIR / "backend" / "generators" / "k8s_psa_namespaces.tf.j2").read_text()).render(
                            namespaces=namespaces,
                            environment=psa_environment,
                            team_label=psa_team_label,
                            enforce_level=enforce_level,
                            audit_level=audit_level,
                            warn_level=warn_level,
                            psa_version=psa_version,
                            backend=backend_context,
                        )
                        fname = "k8s_psa_namespaces.tf"
                        (GEN_DIR / fname).write_text(rendered)
                        _store_generation_output("generation", fname, rendered)
        elif resource == "PodSecurity Baseline":
            with st.form("k8s_psp_form"):
                policy_actual_name = st.text_input("PodSecurityPolicy name", value="restricted")
                service_account_namespace = st.text_input("Service account namespace", value="default")
                service_account_name = st.text_input("Service account name", value="default")
                namespace_actual = st.text_input("Namespace to label", value="apps")
                with st.expander("Remote state backend (optional)", expanded=False):
                    k8s_include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_psp_backend_toggle",
                    )
                    k8s_backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not k8s_include_backend,
                        key="k8s_psp_backend_endpoint",
                    )
                    k8s_backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{policy_actual_name}-psp-tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_psp_backend_bucket",
                    )
                    k8s_backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not k8s_include_backend,
                        key="k8s_psp_backend_region",
                    )
                    k8s_backend_key = st.text_input(
                        "State object key",
                        value=f"security/{policy_actual_name}.tfstate",
                        disabled=not k8s_include_backend,
                        key="k8s_psp_backend_key",
                    )
                k8s_backend_context = None
                if k8s_include_backend:
                    k8s_backend_context = {
                        "endpoint": k8s_backend_endpoint,
                        "bucket": k8s_backend_bucket,
                        "region": k8s_backend_region,
                        "key": k8s_backend_key,
                    }
                submitted = st.form_submit_button("Generate PodSecurity baseline .tf", type="primary")
                if submitted:
                    rendered = Template((BASE_DIR / "backend" / "generators" / "k8s_pod_security_baseline.tf.j2").read_text()).render(
                        policy_name="psp",
                        policy_actual_name=policy_actual_name,
                        service_account_namespace=service_account_namespace,
                        service_account_name=service_account_name,
                        namespace_name="psp_ns",
                        namespace_actual=namespace_actual,
                        backend=k8s_backend_context,
                    )
                    fname = f"k8s_pod_security_{policy_actual_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        elif resource == "HPA + PDB":
            with st.form("k8s_hpa_form"):
                namespace_actual = st.text_input("Namespace", value="apps")
                environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=0, key="k8s_hpa_env")
                deployment_name = st.text_input("Target deployment name", value="my-app")
                app_label = st.text_input("App label (selector)", value="my-app")
                min_replicas = st.number_input("Min replicas", value=2, min_value=1, step=1)
                max_replicas = st.number_input("Max replicas", value=6, min_value=2, step=1)
                target_cpu_utilization = st.number_input("Target CPU utilization (%)", value=60, min_value=1, max_value=100, step=5)
                target_memory_input = st.text_input("Target memory utilization (%) (optional)", value="")
                pdb_mode = st.radio("Disruption budget mode", ["min_available", "max_unavailable"], horizontal=True)
                pdb_value = st.text_input("PDB value", value="1")
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_hpa_backend_toggle",
                    )
                    backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not include_backend,
                        key="k8s_hpa_backend_endpoint",
                    )
                    backend_bucket = st.text_input(
                        "State bucket",
                        value=f"{namespace_actual}-tfstate",
                        disabled=not include_backend,
                        key="k8s_hpa_backend_bucket",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not include_backend,
                        key="k8s_hpa_backend_region",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{namespace_actual}/{deployment_name}_hpa.tfstate",
                        disabled=not include_backend,
                        key="k8s_hpa_backend_key",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "endpoint": backend_endpoint,
                        "bucket": backend_bucket,
                        "region": backend_region,
                        "key": backend_key,
                    }
                submitted = st.form_submit_button("Generate HPA + PDB .tf", type="primary")
                if submitted:
                    t = Template((BASE_DIR / "backend" / "generators" / "k8s_hpa_pdb.tf.j2").read_text())
                    rendered = t.render(
                        resource_name=deployment_name.replace("-", "_"),
                        namespace_actual=namespace_actual,
                        environment=environment,
                        deployment_name=deployment_name,
                        app_label=app_label,
                        min_replicas=int(min_replicas),
                        max_replicas=int(max_replicas),
                        target_cpu_utilization=int(target_cpu_utilization),
                        target_memory_utilization=target_memory_input.strip(),
                        pdb_min_available=pdb_value if pdb_mode == "min_available" else "",
                        pdb_max_unavailable=pdb_value if pdb_mode == "max_unavailable" else "",
                        backend=backend_context,
                    )
                    fname = f"k8s_hpa_{deployment_name.replace('-', '_')}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)
        else:
            with st.form("k8s_argocd_form"):
                col1, col2 = st.columns(2)
                with col1:
                    namespace_actual = st.text_input("Namespace", value="argocd", key="k8s_argocd_ns")
                    environment = st.selectbox("Environment", ["dev", "stage", "prod"], index=2, key="k8s_argocd_env")
                    team_label = st.text_input("Team label", value="platform", key="k8s_argocd_team")
                    release_name = st.text_input("Helm release name", value="argocd", key="k8s_argocd_release")
                with col2:
                    chart_version = st.text_input("Chart version", value="5.46.6", key="k8s_argocd_version")
                    helm_repository = st.text_input(
                        "Helm repository URL",
                        value="https://argoproj.github.io/argo-helm",
                        key="k8s_argocd_repo",
                    )
                    controller_replicas = st.number_input("Controller replicas", value=2, min_value=1, step=1)
                    allowed_cidrs_input = st.text_input(
                        "Allowed CIDRs for control plane access (comma separated)",
                        value="10.0.0.0/24",
                        key="k8s_argocd_cidrs",
                    )
                enable_appset = st.checkbox("Enable ApplicationSet controller", value=True, key="k8s_argocd_appset")
                enable_dex = st.checkbox("Enable Dex SSO service", value=False, key="k8s_argocd_dex")
                disable_admin = st.checkbox("Disable built-in admin account", value=True, key="k8s_argocd_admin_disable")
                enable_ingress = st.checkbox("Configure ingress for Argo CD server", value=False, key="k8s_argocd_ingress")
                ingress_host = st.text_input(
                    "Ingress host (FQDN)",
                    value="argocd.example.com",
                    disabled=not enable_ingress,
                    key="k8s_argocd_ingress_host",
                )
                ingress_class = st.text_input(
                    "Ingress class name",
                    value="nginx",
                    disabled=not enable_ingress,
                    key="k8s_argocd_ingress_class",
                )
                tls_secret_name = st.text_input(
                    "TLS secret name",
                    value="argocd-server-tls",
                    disabled=not enable_ingress,
                    key="k8s_argocd_tls_secret",
                )
                external_url = st.text_input(
                    "External URL (used in Argo CD config)",
                    value="https://argocd.example.com" if enable_ingress else "",
                    key="k8s_argocd_external_url",
                )
                set_resource_quota = st.checkbox(
                    "Apply namespace resource quota",
                    value=True,
                    key="k8s_argocd_quota_toggle",
                )
                quota_col1, quota_col2 = st.columns(2)
                with quota_col1:
                    quota_limits_cpu = st.text_input("Quota limits.cpu", value="20", disabled=not set_resource_quota)
                    quota_limits_memory = st.text_input("Quota limits.memory", value="64Gi", disabled=not set_resource_quota)
                with quota_col2:
                    quota_requests_cpu = st.text_input("Quota requests.cpu", value="10", disabled=not set_resource_quota)
                    quota_requests_memory = st.text_input(
                        "Quota requests.memory",
                        value="32Gi",
                        disabled=not set_resource_quota,
                    )
                quota_pods = st.text_input(
                    "Quota pods",
                    value="200",
                    disabled=not set_resource_quota,
                    key="k8s_argocd_quota_pods",
                )
                with st.expander("Remote state backend (optional)", expanded=False):
                    include_backend = st.checkbox(
                        'Emit terraform backend "s3" (MinIO/S3-compatible)',
                        value=False,
                        key="k8s_argocd_backend_toggle",
                    )
                    backend_endpoint = st.text_input(
                        "S3/MinIO endpoint",
                        value="https://minio.example.com",
                        disabled=not include_backend,
                        key="k8s_argocd_backend_endpoint",
                    )
                    backend_bucket = st.text_input(
                        "State bucket",
                        value="tfstate",
                        disabled=not include_backend,
                        key="k8s_argocd_backend_bucket",
                    )
                    backend_region = st.text_input(
                        "State region",
                        value="us-east-1",
                        disabled=not include_backend,
                        key="k8s_argocd_backend_region",
                    )
                    backend_key = st.text_input(
                        "State object key",
                        value=f"{environment}/k8s/argocd.tfstate",
                        disabled=not include_backend,
                        key="k8s_argocd_backend_key",
                    )
                backend_context = None
                if include_backend:
                    backend_context = {
                        "endpoint": backend_endpoint,
                        "bucket": backend_bucket,
                        "region": backend_region,
                        "key": backend_key,
                    }
                submitted = st.form_submit_button("Generate Argo CD .tf", type="primary")
                if submitted:
                    def _sanitize(value: str, fallback: str) -> str:
                        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", value or fallback)
                        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
                        if not sanitized:
                            sanitized = fallback
                        if sanitized[0].isdigit():
                            sanitized = f"r_{sanitized}"
                        return sanitized.lower()

                    namespace_resource_name = _sanitize(namespace_actual, "argocd_ns")
                    release_resource_name = _sanitize(release_name, "argocd_release")
                    allowed_cidrs = [cidr.strip() for cidr in allowed_cidrs_input.split(",") if cidr.strip()]
                    template_path = BASE_DIR / "backend" / "generators" / "k8s_argo_cd_baseline.tf.j2"
                    rendered = Template(template_path.read_text()).render(
                        environment=environment,
                        team_label=team_label,
                        namespace_actual=namespace_actual,
                        namespace_resource_name=namespace_resource_name,
                        release_name=release_name,
                        release_resource_name=release_resource_name,
                        helm_repository=helm_repository,
                        chart_version=chart_version,
                        controller_replicas=int(controller_replicas),
                        enable_appset=enable_appset,
                        enable_dex=enable_dex,
                        disable_admin=disable_admin,
                        enable_ingress=enable_ingress,
                        ingress_host=ingress_host if enable_ingress else "",
                        ingress_class=ingress_class if enable_ingress else "",
                        tls_secret_name=tls_secret_name if enable_ingress else "",
                        external_url=external_url,
                        allowed_cidrs=allowed_cidrs,
                        set_resource_quota=set_resource_quota,
                        quota_limits_cpu=quota_limits_cpu if set_resource_quota else "",
                        quota_limits_memory=quota_limits_memory if set_resource_quota else "",
                        quota_requests_cpu=quota_requests_cpu if set_resource_quota else "",
                        quota_requests_memory=quota_requests_memory if set_resource_quota else "",
                        quota_pods=quota_pods if set_resource_quota else "",
                        backend=backend_context,
                    )
                    fname = f"k8s_argocd_{namespace_resource_name}.tf"
                    (GEN_DIR / fname).write_text(rendered)
                    _store_generation_output("generation", fname, rendered)

        _render_generation_output("generation")

# ------------------------------ Review ------------------------------
with tab2:
    st.subheader("Review Terraform for best practices / security standards")
    st.caption("Upload `.tf` files (drag multiple) or a .zip of a folder. Optionally run terraform validate if available.")
    st.markdown(
        """
        <div class="tm-highlight-card">
            <h4>Review workflow</h4>
            <ul>
                <li>Drop Terraform files or zip archives to inspect across multiple modules at once.</li>
                <li>Enable Terraform validate or AI assistance when you need extra safety nets.</li>
                <li>Download the JSON report to plug into CI/CD or share with delivery teams.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    llm_options = None
    stored_llm = get_llm_settings()
    llm_provider = stored_llm.get("provider", "off")
    llm_model = stored_llm.get("model", DEFAULT_OPENAI_MODEL)
    llm_explanations = bool(stored_llm.get("enable_explanations", False))
    llm_patches = bool(stored_llm.get("enable_patches", False))

    col_upload, col_meta = st.columns([1.4, 1])
    temp_dir = BASE_DIR / ".uploads"
    temp_dir.mkdir(exist_ok=True)
    files_to_scan: List[Path] = []

    with col_upload:
        with st.container():
            st.markdown(
                """
                <div class="tm-review-card">
                    <h4>Upload Terraform</h4>
                    <p>Drop single <code>.tf</code> files or zipped modules to scan complete stacks.</p>
                """,
                unsafe_allow_html=True,
            )
            uploaded_files = st.file_uploader(
                "Upload .tf files or a .zip",
                accept_multiple_files=True,
                type=["tf", "zip"],
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        if uploaded_files:
            for uf in uploaded_files:
                data = uf.read()
                if uf.name.endswith(".zip"):
                    import zipfile

                    zpath = temp_dir / uf.name
                    zpath.write_bytes(data)
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        target_dir = temp_dir / uf.name.replace(".zip", "")
                        z.extractall(target_dir)
                        for p in target_dir.rglob("*.tf"):
                            files_to_scan.append(p)
                else:
                    p = temp_dir / uf.name
                    p.write_bytes(data)
                    files_to_scan.append(p)

        if files_to_scan:
            display_files = files_to_scan[:6]
            extra_count = max(len(files_to_scan) - len(display_files), 0)
            items = "".join(
                f"<li><code>{html.escape(path.name)}</code></li>"
                for path in display_files
            )
            if extra_count:
                items += f"<li>+{extra_count} more file(s)</li>"
            queue_html = f"<ul class='tm-review-queue'>{items}</ul>"
        else:
            queue_html = "<p class='tm-review-placeholder'>Waiting for Terraform files or archives...</p>"

        st.markdown(
            f"""
            <div class="tm-review-card tm-review-card--compact">
                <h4>Queued files</h4>
                {queue_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.markdown(
                """
                <div class="tm-review-card tm-review-card--compact tm-review-options">
                    <h4>Analysis options</h4>
                """,
                unsafe_allow_html=True,
            )
            use_tf_validate = st.checkbox(
                "Attempt `terraform validate` (if terraform is installed)",
                value=False,
                key="review_tf_validate",
            )
            with st.expander("AI assistance (optional)", expanded=False):
                provider_options = ["Off", "OpenAI (default)", "Azure OpenAI (preview)"]
                llm_provider_map = {
                    "Off": "off",
                    "OpenAI (default)": "openai",
                    "Azure OpenAI (preview)": "azure",
                }
                default_provider_label = next(
                    (label for label, slug in llm_provider_map.items() if slug == llm_provider),
                    "Off",
                )
                llm_choice = st.selectbox(
                    "Provider",
                    provider_options,
                    index=provider_options.index(default_provider_label),
                    help="Toggle AI-authored explanations and patch suggestions. Detected findings remain deterministic.",
                    key="review_llm_provider",
                )
                llm_provider = llm_provider_map[llm_choice]
                llm_model = st.text_input(
                    "Model / deployment name",
                    value=llm_model,
                    disabled=llm_provider == "off",
                    help="OpenAI: model name (e.g. gpt-4.1-mini). Azure: provide the deployment name once configured.",
                    key="review_llm_model",
                )
                llm_explanations = st.checkbox(
                    "Attach AI explanations",
                    value=llm_explanations,
                    disabled=llm_provider == "off",
                    help="Adds AI-written Why/Impact/Fix context alongside deterministic findings.",
                    key="review_llm_explanations",
                )
                llm_patches = st.checkbox(
                    "Suggest AI patch diffs",
                    value=llm_patches,
                    disabled=llm_provider == "off",
                    help="Drafts diffs for review; never auto-applies them.",
                    key="review_llm_patches",
                )
                if llm_provider != "off":
                    st.caption(
                        "Requires `OPENAI_API_KEY` (or Azure OpenAI credentials) in the Streamlit environment. AI output is advisory only."
                    )
            st.markdown("</div>", unsafe_allow_html=True)

    with col_meta:
        st.markdown(
            """
            <div class="tm-review-card tm-review-card--info">
                <h4>Review checklist</h4>
                <ol class="tm-review-steps">
                    <li>Upload HCL files or a zipped module to stage inputs.</li>
                    <li>Select optional validation hooks or AI assistance.</li>
                    <li>Run the review and inspect findings grouped by rule.</li>
                </ol>
                <div class="tm-review-meta">
                    <span class="tm-meta-chip">Deterministic policy engine</span>
                    <span class="tm-meta-chip">Knowledge base context</span>
                    <span class="tm-meta-chip">Downloadable JSON report</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="tm-review-card tm-review-card--compact">
                <h4>Pro tip</h4>
                <p>Bundle Terraform fixtures under <code>sample/</code> to regression-test new checks locally.</p>
                <div class="tm-review-meta">
                    <span class="tm-meta-chip">Severity gates controlled by <code>tfreview.yaml</code></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    current_llm = {
        "provider": llm_provider,
        "model": llm_model.strip() or stored_llm.get("model", DEFAULT_OPENAI_MODEL),
        "enable_explanations": bool(llm_explanations),
        "enable_patches": bool(llm_patches),
    }
    update_llm_settings(current_llm)

    if current_llm["provider"] in {"openai", "azure"} and (
        current_llm["enable_explanations"] or current_llm["enable_patches"]
    ):
        llm_options = current_llm

    if st.button("Run review", type="primary", disabled=not files_to_scan):
        report = scan_paths(
            files_to_scan,
            use_terraform_validate=use_tf_validate,
            llm_options=llm_options,
        )
        summary = report.get("summary", {})
        thresholds = summary.get("thresholds", {})
        severity_counts = summary.get("severity_counts", {})

        st.success(f"Scan complete: {summary.get('issues_found', 0)} issues found across {summary.get('files_scanned', 0)} files.")

        overview_cols = st.columns(3)
        runtime_seconds = summary.get("elapsed_seconds")
        runtime_display = (
            f"{runtime_seconds:.2f}" if isinstance(runtime_seconds, (int, float)) else "--"
        )
        overview_cols[0].markdown(
            f'<div class="tm-stat-card"><span>Issues Found</span><strong>{summary.get("issues_found", 0)}</strong></div>',
            unsafe_allow_html=True,
        )
        overview_cols[1].markdown(
            f'<div class="tm-stat-card"><span>Files Scanned</span><strong>{summary.get("files_scanned", 0)}</strong></div>',
            unsafe_allow_html=True,
        )
        overview_cols[2].markdown(
            f'<div class="tm-stat-card"><span>Runtime (s)</span><strong>{runtime_display}</strong></div>',
            unsafe_allow_html=True,
        )

        if severity_counts:
            severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
            visible_severities = [sev for sev in severity_order if sev in severity_counts]
            if not visible_severities:
                visible_severities = list(severity_counts.keys())
            chips = []
            for severity in visible_severities:
                class_suffix = severity.lower()
                valid_suffixes = {"critical", "high", "medium", "low", "info"}
                class_name = f" tm-severity-chip--{class_suffix}" if class_suffix in valid_suffixes else ""
                chips.append(
                    f"<span class='tm-severity-chip{class_name}'>{severity.title()}&nbsp;&bull;&nbsp;{severity_counts.get(severity, 0)}</span>"
                )
            st.markdown(
                f"<div class='tm-review-meta'>{''.join(chips)}</div>",
                unsafe_allow_html=True,
            )

        llm_meta = report.get("llm") or {}
        if llm_meta.get("provider") and llm_meta.get("provider") != "off":
            meta_chips = [
                f"<span class='tm-meta-chip'>Provider: {llm_meta.get('provider')}</span>",
                f"<span class='tm-meta-chip'>Model: {llm_meta.get('model')}</span>",
            ]
            if llm_meta.get("explanations_enabled"):
                meta_chips.append(
                    f"<span class='tm-meta-chip'>Explanations {llm_meta.get('explanations_completed', 0)}/{llm_meta.get('explanations_requested', 0)}</span>"
                )
            if llm_meta.get("patches_enabled"):
                meta_chips.append(
                    f"<span class='tm-meta-chip'>Patches {llm_meta.get('patches_completed', 0)}/{llm_meta.get('patches_requested', 0)}</span>"
                )
            st.markdown(
                f"<div class='tm-review-meta'>{''.join(meta_chips)}</div>",
                unsafe_allow_html=True,
            )
            if llm_meta.get("errors"):
                st.warning("AI assistance hit a snag. Deterministic findings are still available below.")
                with st.expander("LLM error details"):
                    for err in llm_meta["errors"]:
                        st.code(err, language="text")

        if thresholds.get("configured"):
            fail_on = ", ".join(thresholds.get("fail_on", [])) or "configured severities"
            violated = ", ".join(thresholds.get("violated_ids", [])) or "none"
            if thresholds.get("triggered"):
                st.error(
                    f"Severity gate triggered (fail_on={fail_on}). Offending findings: {violated}. "
                    "Update `tfreview.yaml` or remediate the findings to pass."
                )
            else:
                st.info(f"Severity gate (fail_on={fail_on}) did not trigger.")

        rows = [
            {
                "ID": f["id"],
                "Severity": f["severity"],
                "Title": f["title"],
                "File": Path(f["file"]).name,
                "Rule": f["rule"],
                "Line": f.get("line", ""),
            }
            for f in report["findings"]
        ]
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        for f in report["findings"]:
            with st.expander(f"{f['severity']} • {f['title']} • {Path(f['file']).name}:{f.get('line','?')}"):
                st.markdown(f"**Rule:** `{f['rule']}`  ")
                st.write(f["description"])
                st.markdown("**Recommendation**")
                st.write(f.get("recommendation",""))
                if f.get("snippet"):
                    st.markdown("**Offending snippet**")
                    st.code(f["snippet"], language="hcl")
                if f.get("suggested_fix_snippet"):
                    st.markdown("**Suggested fix snippet**")
                    st.code(f["suggested_fix_snippet"], language="hcl")
                if f.get("unified_diff"):
                    st.markdown("**Unified diff (illustrative)**")
                    st.code(f["unified_diff"], language="diff")
                if f.get("explanation"):
                    st.markdown("**Why this matters (from local knowledge base)**")
                    st.text(f["explanation"])
                ai_expl = f.get("explanation_ai")
                if ai_expl:
                    st.markdown("**AI Explanation (preview)**")
                    if ai_expl.get("why"):
                        st.markdown(f"- **Why:** {ai_expl['why']}")
                    if ai_expl.get("impact"):
                        st.markdown(f"- **Impact:** {ai_expl['impact']}")
                    if ai_expl.get("how_to_fix"):
                        st.markdown(f"- **How to fix:** {ai_expl['how_to_fix']}")
                    if ai_expl.get("kb_refs"):
                        refs = ", ".join(ai_expl["kb_refs"])
                        st.caption(f"KB refs: {refs}")
                    if ai_expl.get("example_diff"):
                        st.markdown("**AI example diff**")
                        st.code(ai_expl["example_diff"], language="diff")
                    attribution = ai_expl.get("attribution", {})
                    details = []
                    if attribution.get("provider"):
                        details.append(attribution["provider"])
                    if attribution.get("model"):
                        details.append(attribution["model"])
                    if attribution.get("confidence"):
                        details.append(f"confidence={attribution['confidence']}")
                    if attribution.get("cached"):
                        details.append("cached")
                    if details:
                        st.caption("AI assistance via " + " • ".join(details))
                patch_ai = f.get("patch_ai")
                if patch_ai:
                    st.markdown("**AI Patch Suggestion (preview)**")
                    if patch_ai.get("summary"):
                        st.write(patch_ai["summary"])
                    if patch_ai.get("diff"):
                        st.code(patch_ai["diff"], language="diff")
                    validation = patch_ai.get("validation") or {}
                    validation_status = validation.get("status")
                    if validation_status:
                        details = validation.get("details")
                        label = f"Validation: {validation_status}"
                        if details:
                            label += f" — {details}"
                        st.caption(label)

        st.download_button(
            "Download JSON report",
            data=json.dumps(report, indent=2).encode(),
            file_name="terraform_review_report.json",
            mime="application/json",
        )

# ------------------------------ Knowledge ------------------------------
with tab3:
    st.subheader("Search local knowledge base (powers the explanations)")
    st.caption("Look up remediation notes, architectural decisions, and security standards indexed from Markdown in `knowledge/`.")
    st.markdown(
        """
        <div class="tm-highlight-card">
            <h4>Search tips</h4>
            <ul>
                <li>Search by rule ID (e.g. <code>AWS.S3.Encryption</code>) to jump to the relevant explainer.</li>
                <li>Combine technologies and controls: <code>azure key vault purge protection</code>.</li>
                <li>Add new Markdown under <code>knowledge/</code> then run <code>python -m backend.cli reindex</code>.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    q = st.text_input("Query", value="terraform syntax variables modules")
    topk = st.slider("Top K", min_value=1, max_value=5, value=2)
    if st.button("Search KB"):
        docs = retrieve(q, top_k=topk)
        if not docs:
            st.info("No documents matched. Try broadening the query or add more Markdown under `knowledge/`.")
        for name, text in docs:
            with st.container():
                st.markdown(f'<div class="tm-doc-snippet"><h4>{name}</h4>', unsafe_allow_html=True)
                st.code(text[:800], language="markdown")
                if len(text) > 800:
                    st.caption("Preview truncated - open the Markdown file for full context.")
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("Tip: add your org standards as Markdown in `knowledge/` to customize explanations.")
