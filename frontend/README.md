# ActivityLogger Frontend

React-based frontend for ActivityLogger application.

## Components

### Pages
- `RecordingPage`: Audio capture and activity logging
- `ReportsPage`: View and generate activity reports
- `SettingsPage`: Configure categories and preferences

### Features
- Web Audio API for voice recording
- Real-time activity logging
- Report visualization with Markdown support
- Dynamic settings management

## Development

### Local Setup
```bash
# Install dependencies
npm install

# Start development server
npm start
```

### Available Scripts
```bash
# Run development server
npm start

# Run tests
npm test

# Create production build
npm run build

# Analyze bundle size
npm run analyze
```

### Environment Configuration
```bash
# .env.development
REACT_APP_API_URL=http://localhost:8000
REACT_APP_ENABLE_DEBUG=true

# .env.production
REACT_APP_API_URL=http://your-production-api
REACT_APP_ENABLE_DEBUG=false
```

### Project Structure
```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Main page components
│   ├── hooks/         # Custom React hooks
│   ├── utils/         # Helper functions
│   ├── api/           # API client functions
│   └── App.js         # Root component
├── public/            # Static assets
└── package.json       # Project configuration
```

## Building for Production

```bash
# Create optimized production build
npm run build

# Test production build locally
npx serve -s build
```

## Testing

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Generate coverage report
npm test -- --coverage
```

## Troubleshooting

### Common Issues
1. Port 3000 already in use:
```bash
# Find process using port 3000
lsof -i :3000
# Kill process
kill -9 <PID>
```

2. Node modules issues:
```bash
# Clean install
rm -rf node_modules
rm package-lock.json
npm install
```

## Learn More

- [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started)
- [React documentation](https://reactjs.org/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)