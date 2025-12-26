# PDF Letter Processor - Web Application

A self-contained web application for processing PDF contribution letters. This application splits a master PDF into individual family letters and creates an even-page version suitable for duplex printing.

## Features

- **Web-based Interface**: Simple drag-and-drop or click-to-upload interface
- **Bot Protection**: Google reCAPTCHA v3 integration to prevent automated abuse
- **PDF Splitting**: Automatically splits a master PDF into individual family letters based on "Page X of Y" footers
- **Even-Page Generation**: Creates a version of the PDF with blank pages inserted to ensure each letter has an even number of pages (ideal for duplex printing)
- **Automated Naming**: Individual PDFs are named using envelope numbers and family names extracted from the letters
- **ZIP Download**: All processed PDFs are packaged into a single ZIP file for easy download

## reCAPTCHA Configuration

This application uses Google reCAPTCHA v3 to prevent bot submissions. To enable reCAPTCHA protection:

### 1. Get reCAPTCHA Keys

1. Go to [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin/create)
2. Choose **reCAPTCHA v3**
3. Add your domain (e.g., `ps-pdf.squyres.com`)
4. For localhost testing, add `localhost`
5. Get your **Site Key** and **Secret Key**

### 2. Set Environment Variables

The application requires two environment variables:

- `RECAPTCHA_SITE_KEY`: Your reCAPTCHA site key (public)
- `RECAPTCHA_SECRET_KEY`: Your reCAPTCHA secret key (private)

**Note**: If these environment variables are not set, the application will log a warning and skip reCAPTCHA verification (useful for development, but not recommended for production).

## Container Setup

### Building the Docker Image

```bash
cd ps-queries/ps-contribution-web-app
docker build -t pdf-letter-processor .
```

### Running the Container

#### Basic Run (without persistent logs)

```bash
docker run -d \
  -p 5000:5000 \
  -e RECAPTCHA_SITE_KEY='your_site_key_here' \
  -e RECAPTCHA_SECRET_KEY='your_secret_key_here' \
  --name pdf-processor \
  pdf-letter-processor
```

#### Run with Persistent Logs

To preserve web server logs even after the container is stopped or removed, map the log directory to your host:

```bash
docker run -d \
  -p 5000:5000 \
  -e RECAPTCHA_SITE_KEY='your_site_key_here' \
  -e RECAPTCHA_SECRET_KEY='your_secret_key_here' \
  -v /path/on/host/logs:/var/log/pdf-processor \
  --name pdf-processor \
  pdf-letter-processor
```

Replace `/path/on/host/logs` with an actual directory on your host system, for example:

```bash
# macOS/Linux example
docker run -d \
  -p 5000:5000 \
  -e RECAPTCHA_SITE_KEY='your_site_key_here' \
  -e RECAPTCHA_SECRET_KEY='your_secret_key_here' \
  -v ~/pdf-processor-logs:/var/log/pdf-processor \
  --name pdf-processor \
  pdf-letter-processor
```

#### Run with Custom Port

```bash
docker run -d \
  -p 8080:5000 \
  -e RECAPTCHA_SITE_KEY='your_site_key_here' \
  -e RECAPTCHA_SECRET_KEY='your_secret_key_here' \
  -v ~/pdf-processor-logs:/var/log/pdf-processor \
  --name pdf-processor \
  pdf-letter-processor
```

This will make the application available on port 8080 on your host.

## Accessing the Application

Once the container is running, open your web browser and navigate to:

```
http://localhost:5000
```

Or if you mapped to a different port:

```
http://localhost:8080
```

## Using the Application

1. **Upload PDF**: Click the upload area or drag and drop a PDF file
2. **Process**: Click the "Process PDF" button
3. **Wait**: The application will show a processing indicator
4. **Download**: Once complete, click "Download ZIP File" to get your processed letters

## Container Management

### View Logs

#### Live logs
```bash
docker logs -f pdf-processor
```

#### Access log files (if using persistent volume)
```bash
# On your host system
tail -f ~/pdf-processor-logs/access.log
tail -f ~/pdf-processor-logs/error.log
```

### Stop the Container

```bash
docker stop pdf-processor
```

### Start the Container

```bash
docker start pdf-processor
```

### Remove the Container

```bash
docker stop pdf-processor
docker rm pdf-processor
```

### Restart the Container

```bash
docker restart pdf-processor
```

## Output Structure

The downloaded ZIP file contains:

```
processed_letters.zip
├── individual-letters/
│   ├── 12345_John_Doe.pdf
│   ├── 12346_Jane_Smith.pdf
│   └── ...
└── even_page_letters.pdf
```

- **individual-letters/**: Directory containing one PDF per family letter
  - Files are named with format: `{envelope_number}_{family_name}.pdf`
- **even_page_letters.pdf**: Single PDF with blank pages inserted to make each letter an even number of pages

## Technical Details

### Components

- **Flask**: Web framework
- **Gunicorn**: Production-grade WSGI HTTP server (4 workers)
- **pypdf**: PDF manipulation library
- **pdfplumber**: PDF text extraction library

### Processing Logic

1. **Letter Detection**: Uses "Page X of Y" footer pattern to identify letter boundaries
2. **Information Extraction**: Extracts envelope number and family name from the first page
3. **Individual PDFs**: Creates separate PDF files for each family letter
4. **Even-Page PDF**: Analyzes page counts and inserts blank pages after odd-page letters
5. **ZIP Creation**: Packages all files for convenient download

### Timeouts and Limits

- Upload size limit: 100MB
- Request timeout: 300 seconds (5 minutes)
- Worker processes: 4

## Troubleshooting

### Container won't start

Check logs:
```bash
docker logs pdf-processor
```

### Can't access the web interface

1. Verify container is running: `docker ps`
2. Check port mapping: Ensure `-p 5000:5000` matches your browser URL
3. Check firewall settings on host

### Processing fails

1. Check error logs in the mapped volume directory
2. Ensure PDF has "Page X of Y" footers on each page
3. Verify PDF is not corrupted or password-protected

### Permission issues with log directory

```bash
# On Linux/macOS, ensure the log directory has proper permissions
mkdir -p ~/pdf-processor-logs
chmod 755 ~/pdf-processor-logs
```

## Development Mode

To run the application without Docker (for development):

```bash
# Install dependencies
pip install -r requirements.txt

# Run with Flask development server
python app.py
```

The application will be available at `http://localhost:5000`

## Security Notes

- **Bot Protection**: reCAPTCHA v3 is implemented to prevent automated abuse (requires configuration)
- **Search Engine Protection**: robots.txt endpoint prevents search engine indexing
- **Temporary File Cleanup**: Uploaded PDFs are automatically cleaned up after download
- No user authentication is implemented
- For production use, consider adding:
  - User authentication/authorization
  - HTTPS/TLS (required for reCAPTCHA in production)
  - Rate limiting at reverse proxy level
  - Resource limits and monitoring
  - Regular security updates

## License

This application is provided as-is for internal use.
