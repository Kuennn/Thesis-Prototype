# ExamCheck AI — Frontend

A React-based frontend for the **Hybrid Automated Examination Checking System** thesis project.

## Features

- Drag-and-drop image upload (JPG, PNG, WEBP)
- Multi-file support with live previews
- Per-file status tracking (ready → processing → graded)
- Exam name & subject metadata fields
- Simulated API call — ready to connect to your FastAPI backend

## Project Structure

```
src/
├── components/
│   ├── Navbar.js / .css         # Top navigation bar
│   ├── UploadZone.js / .css     # Drag-and-drop upload area
│   ├── ImagePreviewGrid.js / .css  # File preview cards
│   └── SubmitPanel.js / .css    # Submit button + status
├── pages/
│   └── UploadPage.js / .css     # Main upload page layout
├── App.js / .css                # App shell + simple routing
├── index.js                     # React entry point
└── index.css                    # Global design tokens
```

## Setup

```bash
# Install dependencies
npm install

# Start development server
npm start
```

Runs at: `http://localhost:3000`

## Connecting to Your Backend

In `src/pages/UploadPage.js`, find the `handleSubmit` function.
Uncomment the real API call block and update the URL:

```js
const res = await fetch('http://localhost:8000/api/upload', {
  method: 'POST',
  body: formData,
});
```

Your FastAPI backend should accept `multipart/form-data` with:
- `exam_name` (string)
- `subject` (string)
- `papers` (multiple image files)

## Tech Stack

- React 18
- Plain CSS with CSS variables (no Tailwind dependency)
- Google Fonts: DM Serif Display + DM Sans
