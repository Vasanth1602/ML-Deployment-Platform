# DeployML Frontend

Production-grade React frontend for the Automated ML Deployment Framework.

## Tech Stack

- **React 19** with Vite
- **Tailwind CSS v4** for styling
- **React Router** for navigation
- **Socket.IO Client** for real-time updates
- **Lucide React** for icons
- **shadcn/ui** design patterns

## Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── Sidebar.jsx
│   ├── Navbar.jsx
│   └── StatCard.jsx
├── pages/           # Page components
│   ├── Dashboard.jsx
│   ├── Deploy.jsx
│   ├── Applications.jsx
│   └── Instances.jsx
├── services/        # API and WebSocket services
│   ├── api.js
│   └── socket.js
├── styles/          # Global styles
│   └── globals.css
├── utils/           # Utilities and constants
│   └── constants.js
├── lib/             # Helper functions
│   └── utils.js
├── App.jsx          # Main app component
└── main.jsx         # Entry point
```

## Development

### Prerequisites

- Node.js 18+ installed
- Backend Flask server running on `http://localhost:5000`

### Installation

```bash
npm install
```

### Run Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Environment Variables

Create a `.env` file:

```env
VITE_API_URL=http://localhost:5000
```

## Features Implemented

### Phase 1 ✅
- [x] Project setup with Vite + React
- [x] Tailwind CSS v4 configuration
- [x] Dark theme (Zinc color scheme)
- [x] Folder structure
- [x] API service layer
- [x] WebSocket service layer
- [x] Sidebar navigation
- [x] Top navbar
- [x] Dashboard page with stats
- [x] Routing setup

### Phase 2 (Next)
- [ ] Deployment form component
- [ ] Progress tracker with WebSocket
- [ ] Real-time deployment updates

### Phase 3 (Next)
- [ ] Applications table
- [ ] Instances grid
- [ ] Instance management actions

### Phase 4 (Next)
- [ ] Toast notifications
- [ ] Error handling
- [ ] Loading states
- [ ] Responsive design improvements

## Architecture Decisions

### Service Layer Pattern
All API calls go through `services/api.js` - no direct fetch calls in components.

### WebSocket Management
Centralized WebSocket connection in `services/socket.js` with proper cleanup.

### Component Reusability
Components are designed to be reusable and follow single responsibility principle.

### Type Safety
Using JSDoc comments for better IDE support (can migrate to TypeScript later).

## Design System

### Colors (Dark Theme)
- Background: `hsl(240 10% 3.9%)`
- Foreground: `hsl(0 0% 98%)`
- Primary: `hsl(0 0% 98%)`
- Secondary: `hsl(240 3.7% 15.9%)`
- Muted: `hsl(240 3.7% 15.9%)`
- Border: `hsl(240 3.7% 15.9%)`

### Typography
Using system fonts with proper hierarchy.

### Spacing
Consistent spacing using Tailwind's spacing scale.

## Next Steps

1. **Deploy Page**: Build the deployment form with validation
2. **Progress Tracker**: Real-time deployment progress with WebSocket
3. **Applications Table**: List all deployments with filtering
4. **Instances Grid**: EC2 instance management
5. **Toast System**: User notifications
6. **Error Boundaries**: Graceful error handling
7. **Loading States**: Skeleton screens and spinners
8. **Mobile Responsive**: Optimize for smaller screens

## Notes

- Dark mode is enabled by default (class="dark" on root div)
- All components use functional components with hooks
- No Redux - using React state and context where needed
- Clean separation of concerns between UI, business logic, and data fetching
