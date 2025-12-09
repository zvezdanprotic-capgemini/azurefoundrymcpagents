import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Avatar,
  LinearProgress,
  Divider,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Send,
  Person,
  SmartToy,
  PlayArrow,
  CheckCircle,
  Info,
  Home,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import SessionPanel from './SessionPanel';
import type { SessionData, ChatMessage, WorkflowStep, ChatResponse } from '../types';

interface KYCWorkflowProps {
  onNotification: (message: string, severity: 'success' | 'error' | 'warning' | 'info') => void;
}

const KYCWorkflow: React.FC<KYCWorkflowProps> = ({ onNotification }) => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  const [showCompleteDialog, setShowCompleteDialog] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [lastChatMeta, setLastChatMeta] = useState<ChatResponse | null>(null);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }
    loadSession();
    loadWorkflowSteps();
  }, [sessionId, navigate]);

  useEffect(() => {
    scrollToBottom();
  }, [session?.chat_history]);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadSession = async () => {
    if (!sessionId) return;
    
    try {
      const sessionData = await apiService.getSession(sessionId);
      setSession(sessionData);
      
      if (sessionData.status === 'complete') {
        setShowCompleteDialog(true);
      }
    } catch (error) {
      onNotification('Failed to load session', 'error');
      navigate('/');
    }
  };

  const loadWorkflowSteps = async () => {
    try {
      const response = await apiService.getWorkflowSteps();
      setWorkflowSteps(response.steps);
    } catch (error) {
      console.error('Failed to load workflow steps:', error);
    }
  };

  const sendChatMessage = async () => {
    if (!chatMessage.trim() || !sessionId) return;

    const message: ChatMessage = {
      role: 'user',
      content: chatMessage.trim(),
    };

    try {
      setLoading(true);
      const response = await apiService.sendChatMessage(sessionId, message);
      setLastChatMeta(response);
      await loadSession();
      setChatMessage('');
      
      onNotification('Message sent', 'success');

      if (response.advanced && response.advancement?.to === null) {
        // Workflow complete
        setShowCompleteDialog(true);
        onNotification('Workflow completed successfully!', 'success');
      } else if (response.final) {
        if (response.passed) {
          onNotification(`Step passed. Advanced to ${response.advancement?.to || 'end'}`, 'success');
        } else {
          onNotification('Decision JSON received but no PASS - requires review.', 'warning');
        }
      } else if (!response.final) {
        onNotification('Continuing conversation - no final decision yet.', 'info');
      }
    } catch (error) {
      onNotification('Failed to send message', 'error');
    } finally {
      setLoading(false);
    }
  };

  const getCurrentStepIndex = () => {
    if (!session || !workflowSteps.length) return -1;
    return workflowSteps.findIndex(step => step.id === session.current_step);
  };

  // Create a user-friendly summary from agent decision JSON
  const renderFriendlyDecision = () => {
    if (!lastChatMeta || !lastChatMeta.decision) return null;
    const d: any = lastChatMeta.decision;
    const checks: Array<any> = Array.isArray(d.checks) ? d.checks : [];
    const failed = checks.filter(c => c.status === 'FAIL');
    const passed = checks.filter(c => c.status === 'PASS');

    return (
      <Card sx={{ mt: 2, backgroundColor: 'grey.50' }}>
        <CardContent sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Verification Summary
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Decision: <strong>{d.decision || 'PENDING'}</strong> • Risk: <strong>{d.risk_level || 'N/A'}</strong>
          </Typography>
          {d.reason && (
            <Typography variant="body2" sx={{ mb: 1 }}>
              Reason: {d.reason}
            </Typography>
          )}
          {failed.length > 0 && (
            <>
              <Typography variant="body2" sx={{ mt: 1 }}>
                Items needing attention:
              </Typography>
              {failed.map((c, idx) => (
                <Typography key={idx} variant="caption" display="block">
                  • {c.name.replaceAll('_', ' ')} — {c.detail || 'Requires review'}
                </Typography>
              ))}
            </>
          )}
          {passed.length > 0 && (
            <>
              <Typography variant="body2" sx={{ mt: 1 }}>
                Passed checks:
              </Typography>
              {passed.map((c, idx) => (
                <Typography key={idx} variant="caption" display="block" color="success.main">
                  • {c.name.replaceAll('_', ' ')}
                </Typography>
              ))}
            </>
          )}
          {d.next_action && (
            <Typography variant="body2" sx={{ mt: 2 }}>
              Next action: <strong>{d.next_action.replaceAll('_', ' ')}</strong>
            </Typography>
          )}
        </CardContent>
      </Card>
    );
  };


  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendChatMessage();
    }
  };

  const handleCompleteDialogClose = () => {
    setShowCompleteDialog(false);
  };

  const handleReturnHome = () => {
    setShowCompleteDialog(false);
    navigate('/');
  };

  if (!session) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <LinearProgress sx={{ width: '50%' }} />
      </Box>
    );
  }

  const currentStepIndex = getCurrentStepIndex();

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', display: 'flex', gap: 2 }}>
      {/* Sidebar with workflow progress */}
      <Paper sx={{ width: 300, p: 2, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <IconButton onClick={() => navigate('/')} size="small">
            <Home />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1 }}>
            KYC Progress
          </Typography>
        </Box>
        
        <Card sx={{ mb: 2, p: 2 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Customer
          </Typography>
          <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
            {session.customer.name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {session.customer.email}
          </Typography>
        </Card>

        <Box sx={{ flex: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Workflow Steps
          </Typography>
          
          {workflowSteps.map((step, index) => (
            <Card
              key={step.id}
              sx={{
                mb: 1,
                p: 2,
                backgroundColor: 
                  index < currentStepIndex ? 'success.light' :
                  index === currentStepIndex ? 'primary.light' : 'grey.100',
                opacity: index > currentStepIndex ? 0.6 : 1,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {index < currentStepIndex && <CheckCircle sx={{ color: 'success.dark', mr: 1, fontSize: 20 }} />}
                {index === currentStepIndex && <PlayArrow sx={{ color: 'primary.dark', mr: 1, fontSize: 20 }} />}
                {index > currentStepIndex && <Info sx={{ color: 'grey.500', mr: 1, fontSize: 20 }} />}
                
                <Box>
                  <Typography variant="subtitle2">
                    {step.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {step.description}
                  </Typography>
                </Box>
              </Box>
            </Card>
          ))}
        </Box>

        {/* Manual step buttons removed in unified workflow mode */}
      </Paper>

      {/* Right Panel: Session Details & Documents */}
      {sessionId && (
        <SessionPanel sessionId={sessionId} onNotification={onNotification} />
      )}

      {/* Main chat area */}
      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Chat header */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6">
            Chat Assistant
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Current Step: {session.agent_label || workflowSteps[currentStepIndex]?.name || session.current_step}
          </Typography>
        </Box>

        {/* Chat messages */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
          {session.chat_history.map((message, index) => (
            <Box
              key={index}
              sx={{
                display: 'flex',
                mb: 2,
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  maxWidth: '70%',
                  flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
                }}
              >
                <Avatar
                  sx={{
                    mx: 1,
                    backgroundColor: message.role === 'user' ? 'primary.main' : 'secondary.main',
                  }}
                >
                  {message.role === 'user' ? <Person /> : <SmartToy />}
                </Avatar>
                
                <Card
                  sx={{
                    backgroundColor: 
                      message.role === 'user' ? 'primary.light' : 'grey.100',
                    maxWidth: '100%',
                  }}
                >
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Typography variant="body1">
                      {message.content}
                    </Typography>
                    {message.timestamp && (
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        {new Date(parseFloat(message.timestamp) * 1000).toLocaleTimeString()}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Box>
            </Box>
          ))}
          <div ref={chatEndRef} />
          {lastChatMeta && lastChatMeta.user_message && (
            <Box sx={{ mt: 2 }}>
              <Card sx={{ backgroundColor: 'info.light', border: 1, borderColor: 'info.main' }}>
                <CardContent>
                  <Typography variant="body1" color="text.primary">
                    {lastChatMeta.user_message}
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          )}
          {lastChatMeta && lastChatMeta.decision && (
            <Box sx={{ mt: 2 }}>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" gutterBottom>Technical Details (for staff)</Typography>
              <Card sx={{ p:1 }}>
                <CardContent sx={{ p:1, '&:last-child': { pb:1 } }}>
                  <Typography variant="caption" color="text.secondary">
                    Step: {lastChatMeta.agent_label} | Final: {lastChatMeta.final ? 'Yes' : 'No'} | Passed: {lastChatMeta.final ? (lastChatMeta.passed ? 'PASS' : 'NO PASS') : 'N/A'}
                  </Typography>
                  {lastChatMeta.decision && (
                    <Typography variant="caption" display="block" sx={{ mt:0.5 }}>
                      decision: {lastChatMeta.decision.decision || 'n/a'} | risk: {lastChatMeta.decision.risk_level || 'n/a'} | next_action: {lastChatMeta.decision.next_action || 'n/a'}
                    </Typography>
                  )}
                  {lastChatMeta.advanced && lastChatMeta.advancement && (
                    <Typography variant="caption" display="block" sx={{ mt:0.5 }}>
                      Advanced to: {lastChatMeta.advancement.to || 'Workflow Complete'}
                    </Typography>
                  )}
                </CardContent>
              </Card>
              {renderFriendlyDecision()}
            </Box>
          )}
        </Box>

        {/* Chat input */}
        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              placeholder="Type your message..."
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading || session.status === 'complete'}
              multiline
              maxRows={3}
            />
            <Button
              variant="contained"
              onClick={sendChatMessage}
              disabled={!chatMessage.trim() || loading || session.status === 'complete'}
              sx={{ px: 3 }}
            >
              <Send />
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Completion dialog */}
      <Dialog open={showCompleteDialog} onClose={handleCompleteDialogClose}>
        <DialogTitle>KYC Process Complete</DialogTitle>
        <DialogContent>
          <Typography paragraph>
            Congratulations! Your KYC process has been completed successfully.
            All required steps have been processed and verified.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            You can review the session details or return to the home page.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCompleteDialogClose}>
            Stay Here
          </Button>
          <Button onClick={handleReturnHome} variant="contained">
            Return to Home
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KYCWorkflow;