markdown
# Hotel Management System

A full-stack hotel management application with Flask backend and HTML/CSS/JS frontend.

![Screenshot](screenshot.png) <!-- Add a screenshot if available -->

## Features

- Room management (add, view, filter rooms)
- Booking system with date conflict checking
- Customer management
- Invoice generation
- Admin and staff user roles

## Technologies Used

- **Backend**: Python, Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **Database**: In-memory mock database (for development)
- **PDF Generation**: pdfkit/wkhtmltopdf

## Prerequisites

- Python 3.9+
- wkhtmltopdf (for PDF generation)
- Node.js (optional, for frontend development)

## Installation

1. Clone the repository:
   bash
   git clone https://github.com/yourusername/hotel-management-system.git
   cd hotel-management-system
   

2. Create and activate a virtual environment:
   bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   

3. Install Python dependencies:
   bash
   pip install -r requirements.txt
   

4. Install wkhtmltopdf:
   - **Linux**:
     bash
     sudo apt-get install wkhtmltopdf
     
   - **MacOS**:
     bash
     brew install wkhtmltopdf
     
   - **Windows**: Download from [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html)

## Running the Application

1. Start the Flask backend:
   bash
   python app.py
   

2. Open the frontend in your browser:
   
   http://localhost:5000
   

## Usage

### Default Login Credentials
- **Admin**: 
  - Username: `admin`
  - Password: `admin123`
- **Staff**: 
  - Username: `staff`
  - Password: `staff123`

### Key Functionality
- View and manage rooms
- Create and manage bookings
- Generate invoices for bookings
- Manage customer information

## Project Structure


hotel-management-system/
├── app.py                # Flask backend
├── static/               # Static files (CSS, JS, images)
├── templates/            # HTML templates
├── requirements.txt      # Python dependencies
└── README.md


## Troubleshooting

### PDF Generation Issues
If you get errors about wkhtmltopdf:
1. Verify installation with:
   bash
   wkhtmltopdf --version
   
2. Ensure the binary is in your system PATH
3. Alternatively, modify `app.py` to specify the full path:
   python
   config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')  # Update path as needed
   

### Database Reset
The application uses an in-memory database that resets when the server restarts. To repopulate with sample data, simply restart the Flask server.

## License

[MIT License](LICENSE)


### Key Notes:
1. Removed all Vercel/Netlify specific instructions
2. Focused on local development setup
3. Included detailed installation steps for wkhtmltopdf
4. Added troubleshooting section for common issues
5. Kept the project structure clean and simple

You can customize this further by:
- Adding screenshots
- Including more detailed usage examples
- Adding contribution guidelines
- Expanding the troubleshooting section

Would you like me to add any specific additional sections?
