import React, { useEffect, useState } from 'react';
import { Box, Paper, Typography, Chip, Stack, Divider, Button, LinearProgress, IconButton } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArticleIcon from '@mui/icons-material/Article';
import type { SessionPanelData, BlobDocument } from '../types';
import { apiService } from '../services/api';

interface Props {
  sessionId: string;
  onNotification: (message: string, severity: 'success' | 'error' | 'warning' | 'info') => void;
}

const SessionPanel: React.FC<Props> = ({ sessionId, onNotification }) => {
  const [panel, setPanel] = useState<SessionPanelData | null>(null);
  const [docs, setDocs] = useState<BlobDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadAll = async () => {
    setLoading(true);
    try {
      const pd = await apiService.getSessionPanelData(sessionId);
      setPanel(pd);
      setDocs(pd.documents?.documents || []);
    } catch (err: any) {
      console.error('Failed to load session panel data:', err);
      onNotification(err.response?.data?.detail || 'Failed to load session panel', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await apiService.uploadSessionDocument(sessionId, file, 'other');
      onNotification(`Uploaded: ${res.blob_path}`, 'success');
      // Refresh docs list
      const d = await apiService.listSessionDocuments(sessionId);
      setDocs(d.documents);
    } catch (err: any) {
      console.error('Upload failed:', err);
      onNotification(err.response?.data?.detail || 'Upload failed', 'error');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  return (
    <Paper sx={{ width: 360, p: 2, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">Session Panel</Typography>
        <IconButton aria-label="refresh" onClick={loadAll} disabled={loading}>
          <RefreshIcon />
        </IconButton>
      </Box>

      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Customer & CRM */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">Customer</Typography>
        {panel ? (
          <>
            <Typography variant="body1" sx={{ fontWeight: 'bold' }}>{panel.session.customer.name}</Typography>
            <Typography variant="body2" color="text.secondary">{panel.session.customer.email}</Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <Chip label={`Step: ${panel.session.current_step}`} variant="outlined" size="small" />
              <Chip label={`Status: ${panel.session.status}`} color={panel.session.status === 'in_progress' ? 'info' : 'success'} size="small" />
            </Stack>
            <Divider sx={{ my: 1.5 }} />
            <Typography variant="subtitle2" color="text.secondary">CRM</Typography>
            {panel.crm?.found ? (
              <>
                <Typography variant="body2">Account: {panel.crm.account?.name} (ID: {panel.crm.account?.id})</Typography>
                <Typography variant="body2">Contact: {panel.crm.contact?.first_name} {panel.crm.contact?.last_name} (ID: {panel.crm.contact?.id})</Typography>
              </>
            ) : (
              <Typography variant="body2" color="text.secondary">No CRM record found.</Typography>
            )}
          </>
        ) : (
          <Typography variant="body2" color="text.secondary">Loading session data...</Typography>
        )}
      </Box>

      {/* Previous Sessions */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" color="text.secondary">Previous KYC Sessions</Typography>
        {panel?.previous_sessions?.sessions && panel.previous_sessions.sessions.length > 0 ? (
          panel.previous_sessions.sessions.map(s => (
            <Box key={s.id} sx={{ my: 0.5 }}>
              <Typography variant="caption">{s.id} • {s.status} • {s.current_step}</Typography>
            </Box>
          ))
        ) : (
          <Typography variant="body2" color="text.secondary">No previous sessions.</Typography>
        )}
      </Box>

      {/* Documents */}
      <Box sx={{ mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle2" color="text.secondary">User Documents</Typography>
          <Button component="label" variant="outlined" startIcon={<UploadFileIcon />} disabled={uploading}>
            Upload
            <input type="file" hidden onChange={handleFileInput} />
          </Button>
        </Box>
        <Stack spacing={1} sx={{ mt: 1 }}>
          {docs.length === 0 ? (
            <Typography variant="body2" color="text.secondary">No documents uploaded.</Typography>
          ) : (
            docs.map((d) => (
              <Box key={d.name} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ArticleIcon fontSize="small" color="action" />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>{d.name.split('/').slice(-1)[0]}</Typography>
                  <Typography variant="caption" color="text.secondary">{d.content_type || 'file'} • {d.size} bytes</Typography>
                </Box>
                {d.metadata?.document_type && (
                  <Chip label={d.metadata.document_type} size="small" variant="outlined" />
                )}
              </Box>
            ))
          )}
        </Stack>
      </Box>
    </Paper>
  );
};

export default SessionPanel;
