import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Settings,
  Refresh,
  HealthAndSafety,
} from '@mui/icons-material';

import { useNavigate, useLocation } from 'react-router-dom';

interface HeaderProps {
  healthStatus: string;
  onOpenApiKey: () => void;
  onRefreshHealth: () => void;
}

const Header: React.FC<HeaderProps> = ({
  healthStatus,
  onOpenApiKey,
  onRefreshHealth,
}) => {
  const navigate = useNavigate();
  const location = useLocation();

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <AppBar position="static" elevation={1}>
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', flex: 1 }}>
          <Typography variant="h6" component="div" sx={{ fontWeight: 'bold' }}>
            Azure AI KYC Orchestrator
          </Typography>

          <Box sx={{ ml: 2, display: 'flex', alignItems: 'center' }}>
            <Chip
              icon={<HealthAndSafety />}
              label={`Status: ${healthStatus}`}
              color={getHealthColor(healthStatus)}
              size="small"
              variant="outlined"
              sx={{ backgroundColor: 'rgba(255, 255, 255, 0.1)' }}
            />
            <Tooltip title="Refresh health status">
              <IconButton
                color="inherit"
                onClick={onRefreshHealth}
                size="small"
                sx={{ ml: 1 }}
              >
                <Refresh />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            color="inherit"
            onClick={() => navigate('/')}
            sx={{
              textTransform: 'none',
              fontWeight: location.pathname === '/' ? 'bold' : 'normal',
              borderBottom: location.pathname === '/' ? '2px solid white' : 'none',
              borderRadius: 0
            }}
          >
            Home
          </Button>
          <Button
            color="inherit"
            onClick={() => navigate('/rag')}
            sx={{
              textTransform: 'none',
              fontWeight: location.pathname === '/rag' ? 'bold' : 'normal',
              borderBottom: location.pathname === '/rag' ? '2px solid white' : 'none',
              borderRadius: 0
            }}
          >
            RAG Documents
          </Button>
          <Button
            color="inherit"
            startIcon={<Settings />}
            onClick={onOpenApiKey}
            sx={{ textTransform: 'none' }}
          >
            API Settings
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;