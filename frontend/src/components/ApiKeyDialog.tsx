import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
} from '@mui/material';

interface ApiKeyDialogProps {
  open: boolean;
  onSave: (apiKey: string) => void;
  onClose: () => void;
}

const ApiKeyDialog: React.FC<ApiKeyDialogProps> = ({ open, onSave, onClose }) => {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');

  const handleSave = () => {
    if (!apiKey.trim()) {
      setError('API key is required');
      return;
    }
    
    setError('');
    onSave(apiKey.trim());
    setApiKey('');
  };

  const handleClose = () => {
    setError('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Azure API Configuration</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary" paragraph>
            Enter your Azure API key to enable communication with Azure AI Foundry agents.
            This key will be stored locally in your browser.
          </Typography>
          
          <Alert severity="info" sx={{ mb: 2 }}>
            Your API key is stored securely in your browser's local storage and is only
            used to authenticate requests to the Azure AI services.
          </Alert>
        </Box>

        <TextField
          autoFocus
          margin="dense"
          label="Azure API Key"
          type="password"
          fullWidth
          variant="outlined"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          error={!!error}
          helperText={error}
          placeholder="Enter your Azure API key..."
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ApiKeyDialog;