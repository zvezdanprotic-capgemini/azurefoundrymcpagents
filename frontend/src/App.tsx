import { useState, useEffect } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  Box,
  Alert,
  Snackbar,
} from '@mui/material';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import WelcomePage from './components/WelcomePage';
import KYCWorkflow from './components/KYCWorkflow';
import Header from './components/Header';
import RAGManagement from './components/RAGManagement';
import { apiService } from './services/api';

const theme = createTheme({
  palette: {
    primary: {
      main: '#0078d4',
    },
    secondary: {
      main: '#107c10',
    },
    background: {
      default: '#f3f2f1',
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
  },
});

function App() {
  const [healthStatus, setHealthStatus] = useState<string>('unknown');
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'warning' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'info',
  });

  useEffect(() => {
    // Check health status on startup
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      const health = await apiService.healthCheck();
      setHealthStatus(health.status);
      if (health.status !== 'healthy') {
        showNotification('Some services are degraded', 'warning');
      }
    } catch (error) {
      setHealthStatus('error');
      showNotification('Failed to connect to backend services', 'error');
    }
  };

  const showNotification = (message: string, severity: 'success' | 'error' | 'warning' | 'info') => {
    setNotification({
      open: true,
      message,
      severity,
    });
  };

  const handleCloseNotification = () => {
    setNotification(prev => ({ ...prev, open: false }));
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
          <Header
            healthStatus={healthStatus}
            onOpenApiKey={() => showNotification('API key is configured on the backend', 'info')}
            onRefreshHealth={checkHealth}
          />

          <Container maxWidth="xl" sx={{ flex: 1, py: 3 }}>
            <Routes>
              <Route path="/" element={<WelcomePage />} />
              <Route
                path="/kyc/:sessionId?"
                element={<KYCWorkflow onNotification={showNotification} />}
              />
              <Route
                path="/rag"
                element={<RAGManagement onNotification={showNotification} />}
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Container>

          <Snackbar
            open={notification.open}
            autoHideDuration={6000}
            onClose={handleCloseNotification}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          >
            <Alert
              onClose={handleCloseNotification}
              severity={notification.severity}
              sx={{ width: '100%' }}
            >
              {notification.message}
            </Alert>
          </Snackbar>
        </Box>
      </Router>
    </ThemeProvider>
  );
}

export default App;