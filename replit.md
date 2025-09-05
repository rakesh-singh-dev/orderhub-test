# Gmail Order Tracker

## Overview

The Gmail Order Tracker is a Streamlit web application that connects to Gmail via the Google API to extract and display order information from emails. The application uses OAuth2 authentication to securely access Gmail accounts, searches for order-related emails, and parses them to extract structured order data including order IDs, statuses, delivery dates, and seller information.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Streamlit Framework**: Uses Streamlit for the web interface, providing a simple single-page application with sidebar navigation
- **Session State Management**: Maintains authentication status, Gmail client instance, and parsed order data across user interactions
- **Component Structure**: Modular approach with separate sections for authentication and order extraction functionality

### Authentication System
- **OAuth2 Flow**: Implements Google OAuth2 authentication using the `google-auth-oauthlib` library
- **Token Persistence**: Stores authentication tokens locally in `token.pickle` for session persistence
- **Credential Management**: Uses `credentials.json` file for OAuth2 client configuration

### Email Processing Pipeline
- **Gmail API Integration**: Connects to Gmail using the Google API client library with read-only permissions
- **Email Parsing Engine**: Custom parser that uses regular expressions and BeautifulSoup for HTML content extraction
- **Pattern Recognition**: Multiple regex patterns for identifying order IDs, tracking numbers, delivery dates, and order statuses
- **Data Structure**: Converts extracted email data into structured pandas DataFrames for display and analysis

### Core Components
- **GmailClient**: Handles Gmail API authentication and email fetching operations
- **OrderEmailParser**: Processes email content to extract order-specific information using pattern matching
- **Session Management**: Streamlit session state handles user authentication status and data persistence

## External Dependencies

### Google Services
- **Gmail API**: Primary integration for accessing email data with read-only permissions
- **Google OAuth2**: Authentication service for secure access to user Gmail accounts

### Python Libraries
- **Streamlit**: Web application framework for the user interface
- **Google API Client**: Official Google library for Gmail API interactions (`googleapiclient`)
- **Google Auth Libraries**: OAuth2 authentication handling (`google-auth-oauthlib`, `google-auth`)
- **BeautifulSoup**: HTML parsing for email content extraction
- **Pandas**: Data manipulation and display of parsed order information
- **Standard Libraries**: `re`, `json`, `pickle`, `datetime`, `os` for core functionality

### Configuration Files
- **credentials.json**: Google OAuth2 client credentials (requires user setup)
- **token.pickle**: Automatically generated file for storing authentication tokens