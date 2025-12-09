import React, { useState } from 'react';
import {
  Paper,
  Typography,
  Button,
  TextField,
  Box,
  Grid,
  Card,
  CardContent,
  Stepper,
  Step,
  StepLabel,
  Divider,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { ArrowForward, Security, Psychology, Verified } from '@mui/icons-material';
import { apiService } from '../services/api';
import type { CustomerInput } from '../types';

const workflowSteps = [
  'Customer Intake',
  'Identity Verification', 
  'Eligibility Assessment',
  'Product Recommendation',
  'Compliance Check',
  'Final Action'
];

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<CustomerInput>({
    name: '',
    email: '',
    insurance_needs: '',
  });

  const handleInputChange = (field: keyof CustomerInput) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value,
    }));
  };

  const handleStartKYC = async () => {
    setLoading(true);
    try {
      const response = await apiService.startSession(formData);
      navigate(`/kyc/${response.session_id}`);
    } catch (error) {
      console.error('Failed to start KYC session:', error);
      // Error handling would be done by the notification system in App.tsx
    } finally {
      setLoading(false);
    }
  };

  const isFormValid = formData.name && formData.email && formData.insurance_needs;

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: 3 }}>
      <Grid container spacing={4}>
        {/* Header Section */}
        <Grid item xs={12}>
          <Paper sx={{ p: 4, textAlign: 'center', mb: 4 }}>
            <Typography variant="h3" component="h1" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
              Insurance Employee KYC Portal
            </Typography>
            <Typography variant="h6" color="text.secondary" paragraph>
              AI-assisted customer evaluation and documentation review system
            </Typography>
          </Paper>
        </Grid>

        {/* Features Section */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, textAlign: 'center' }}>
              <Security sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Secure & Compliant
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Enterprise-grade security with full regulatory compliance for insurance industry standards.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, textAlign: 'center' }}>
              <Psychology sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                AI-Powered Intelligence
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Advanced Azure AI agents handle complex decision-making and document processing automatically.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, textAlign: 'center' }}>
              <Verified sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Streamlined Process
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Complete KYC process in minutes with real-time verification and instant approvals.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Workflow Steps */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom sx={{ textAlign: 'center', mb: 3 }}>
              KYC Workflow Process
            </Typography>
            <Stepper orientation="horizontal" sx={{ mb: 2 }}>
              {workflowSteps.map((label, index) => (
                <Step key={index}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          </Paper>
        </Grid>

        {/* Customer Form */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 4 }}>
            <Typography variant="h5" gutterBottom>
              Start New Customer Review
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Enter customer information to begin the AI-assisted KYC evaluation process.
            </Typography>

            <Box component="form" sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label="Customer Full Name"
                value={formData.name}
                onChange={handleInputChange('name')}
                margin="normal"
                required
              />
              
              <TextField
                fullWidth
                label="Customer Email Address"
                type="email"
                value={formData.email}
                onChange={handleInputChange('email')}
                margin="normal"
                required
              />
              
              <TextField
                fullWidth
                label="Insurance Requirements"
                multiline
                rows={3}
                value={formData.insurance_needs}
                onChange={handleInputChange('insurance_needs')}
                margin="normal"
                required
                placeholder="Enter the customer's insurance needs and requirements..."
              />

              <Box sx={{ mt: 3 }}>
                <Button
                  variant="contained"
                  size="large"
                  fullWidth
                  disabled={!isFormValid || loading}
                  onClick={handleStartKYC}
                  endIcon={<ArrowForward />}
                  sx={{ py: 1.5 }}
                >
                  {loading ? 'Initializing Review...' : 'Begin Customer Review'}
                </Button>
              </Box>
            </Box>
          </Paper>
        </Grid>

        {/* Info Section */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 4, height: '100%' }}>
            <Typography variant="h5" gutterBottom>
              Employee Workflow Guide
            </Typography>
            
            <Box sx={{ mt: 3 }}>
              <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
                Automated Processing
              </Typography>
              <Typography variant="body2" paragraph>
                Our AI agents will guide you through each step, automatically processing your information
                and documents with industry-leading accuracy.
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
                Real-time Updates
              </Typography>
              <Typography variant="body2" paragraph>
                Track your application progress in real-time with instant notifications and status updates
                throughout the entire process.
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Typography variant="h6" gutterBottom sx={{ color: 'primary.main' }}>
                Expert Support
              </Typography>
              <Typography variant="body2">
                Get assistance from our AI-powered chat system at any point during your application.
                Human support is available for complex cases.
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default WelcomePage;