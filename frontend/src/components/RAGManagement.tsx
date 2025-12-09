import { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Paper,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Button,
    IconButton,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    MenuItem,
    CircularProgress,
    Stack,
    Alert,
    LinearProgress,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Divider,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArticleIcon from '@mui/icons-material/Article';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { apiService } from '../services/api';
import type { RAGDocument, DocumentChunk } from '../types';

interface NotificationProps {
    onNotification: (message: string, severity: 'success' | 'error' | 'warning' | 'info') => void;
}

const RAGManagement = ({ onNotification }: NotificationProps) => {
    const [documents, setDocuments] = useState<RAGDocument[]>([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Upload dialog state
    const [uploadOpen, setUploadOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [category, setCategory] = useState('general');
    const [chunkSize, setChunkSize] = useState(1000);

    // Delete confirmation state
    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);

    // Chunks viewer state
    const [chunksDialogOpen, setChunksDialogOpen] = useState(false);
    const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
    const [chunks, setChunks] = useState<DocumentChunk[]>([]);
    const [loadingChunks, setLoadingChunks] = useState(false);

    const fetchDocuments = useCallback(async () => {
        setLoading(true);
        try {
            const response = await apiService.listDocuments();
            setDocuments(response.documents);
            setError(null);
        } catch (err: any) {
            console.error('Failed to fetch documents:', err);
            setError('Failed to load documents. Please enable the RAG feature in backend.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchDocuments();
    }, [fetchDocuments]);

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files && event.target.files[0]) {
            setSelectedFile(event.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setUploading(true);
        try {
            // Validate file extension
            const ext = selectedFile.name.split('.').pop()?.toLowerCase();
            if (!['pdf', 'doc', 'docx'].includes(ext || '')) {
                throw new Error('Unsupported file type. Please upload PDF or Word documents.');
            }

            await apiService.uploadDocument(selectedFile, category, chunkSize);
            onNotification(`Successfully uploaded ${selectedFile.name}`, 'success');
            setUploadOpen(false);
            setSelectedFile(null);
            // Refresh list
            fetchDocuments();
        } catch (err: any) {
            console.error('Upload failed:', err);
            onNotification(err.response?.data?.detail || err.message || 'Upload failed', 'error');
        } finally {
            setUploading(false);
        }
    };

    const handleDeleteClick = (filename: string) => {
        setDocumentToDelete(filename);
        setDeleteConfirmOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!documentToDelete) return;

        try {
            await apiService.deleteDocument(documentToDelete);
            onNotification(`Deleted ${documentToDelete}`, 'success');
            fetchDocuments();
        } catch (err: any) {
            console.error('Delete failed:', err);
            onNotification('Failed to delete document', 'error');
        } finally {
            setDeleteConfirmOpen(false);
            setDocumentToDelete(null);
        }
    };

    const handleViewChunks = async (documentId: number, filename: string) => {
        setSelectedDocument(filename);
        setChunksDialogOpen(true);
        setLoadingChunks(true);
        
        try {
            const response = await apiService.getDocumentChunksById(documentId);
            setChunks(response.chunks);
        } catch (err: any) {
            console.error('Failed to load chunks:', err);
            onNotification('Failed to load document chunks', 'error');
            setChunksDialogOpen(false);
        } finally {
            setLoadingChunks(false);
        }
    };

    const getStatusChip = (status: string) => {
        const statusMap: Record<string, { color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning', label: string }> = {
            indexed: { color: 'success', label: 'Indexed' },
            processing: { color: 'info', label: 'Processing' },
            pending: { color: 'warning', label: 'Pending' },
            error: { color: 'error', label: 'Error' },
        };

        const config = statusMap[status] || { color: 'default', label: status };

        return <Chip label={config.label} color={config.color} size="small" />;
    };

    return (
        <Box sx={{ p: 0 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                    RAG Document Management
                </Typography>
                <Stack direction="row" spacing={2}>
                    <Button
                        variant="outlined"
                        startIcon={<RefreshIcon />}
                        onClick={fetchDocuments}
                        disabled={loading}
                    >
                        Refresh
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<UploadFileIcon />}
                        onClick={() => setUploadOpen(true)}
                    >
                        Upload Document
                    </Button>
                </Stack>
            </Box>

            {/* Error Banner */}
            {error && (
                <Alert severity="warning" sx={{ mb: 3 }}>
                    {error}
                </Alert>
            )}

            {/* Documents Table */}
            <TableContainer component={Paper}>
                {loading && <LinearProgress />}
                <Table sx={{ minWidth: 650 }} aria-label="rag documents table">
                    <TableHead>
                        <TableRow>
                            <TableCell>Filename</TableCell>
                            <TableCell>Category</TableCell>
                            <TableCell>Chunks</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Uploaded At</TableCell>
                            <TableCell align="right">Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {!loading && documents.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={6} align="center" sx={{ py: 3 }}>
                                    <Typography variant="body1" color="text.secondary">
                                        No documents found. Upload a PDF or Word file to get started.
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        )}
                        {documents.map((doc) => (
                            <TableRow
                                key={doc.id}
                                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                            >
                                <TableCell component="th" scope="row">
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <ArticleIcon color="action" fontSize="small" />
                                        {doc.filename}
                                    </Box>
                                </TableCell>
                                <TableCell>
                                    <Chip label={doc.category} variant="outlined" size="small" />
                                </TableCell>
                                <TableCell>{doc.chunk_count}</TableCell>
                                <TableCell>{getStatusChip(doc.status)}</TableCell>
                                <TableCell>
                                    {doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : '-'}
                                </TableCell>
                                <TableCell align="right">
                                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                                        <IconButton
                                            aria-label="view chunks"
                                            color="primary"
                                            onClick={() => handleViewChunks(doc.id, doc.filename)}
                                            title="View chunks"
                                        >
                                            <VisibilityIcon />
                                        </IconButton>
                                        <IconButton
                                            aria-label="delete"
                                            color="error"
                                            onClick={() => handleDeleteClick(doc.filename)}
                                            title="Delete document"
                                        >
                                            <DeleteIcon />
                                        </IconButton>
                                    </Stack>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* Upload Dialog */}
            <Dialog open={uploadOpen} onClose={() => !uploading && setUploadOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>Upload RAG Document</DialogTitle>
                <DialogContent>
                    <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
                        <Button
                            variant="outlined"
                            component="label"
                            fullWidth
                            sx={{ height: 100, borderStyle: 'dashed' }}
                        >
                            {selectedFile ? (
                                <Stack alignItems="center">
                                    <ArticleIcon fontSize="large" color="primary" />
                                    <Typography variant="body1">{selectedFile.name}</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                    </Typography>
                                </Stack>
                            ) : (
                                <Stack alignItems="center">
                                    <UploadFileIcon fontSize="large" color="action" />
                                    <Typography>Click to select PDF or Word file</Typography>
                                </Stack>
                            )}
                            <input
                                type="file"
                                hidden
                                accept=".pdf,.doc,.docx"
                                onChange={handleFileSelect}
                            />
                        </Button>

                        <TextField
                            select
                            label="Category"
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            fullWidth
                        >
                            <MenuItem value="general">General</MenuItem>
                            <MenuItem value="policy">Policy</MenuItem>
                            <MenuItem value="compliance">Compliance</MenuItem>
                            <MenuItem value="requirements">Requirements</MenuItem>
                            <MenuItem value="product">Product Info</MenuItem>
                        </TextField>

                        <Box>
                            <Typography gutterBottom>
                                Chunk Size ({chunkSize} chars)
                            </Typography>
                            <TextField
                                type="number"
                                value={chunkSize}
                                onChange={(e) => setChunkSize(Number(e.target.value))}
                                fullWidth
                                inputProps={{ min: 500, max: 4000, step: 100 }}
                                helperText="Size of text chunks for vector embedding (500-4000)"
                            />
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUploadOpen(false)} disabled={uploading}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleUpload}
                        variant="contained"
                        disabled={!selectedFile || uploading}
                    >
                        {uploading ? <CircularProgress size={24} /> : 'Upload & Process'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <Dialog
                open={deleteConfirmOpen}
                onClose={() => setDeleteConfirmOpen(false)}
            >
                <DialogTitle>Delete Document?</DialogTitle>
                <DialogContent>
                    <Typography>
                        Are you sure you want to delete <strong>{documentToDelete}</strong>?
                        This will remove all associated vector embeddings and cannot be undone.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
                    <Button onClick={handleDeleteConfirm} color="error" variant="contained">
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Chunks Viewer Dialog */}
            <Dialog
                open={chunksDialogOpen}
                onClose={() => setChunksDialogOpen(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <ArticleIcon />
                        Document Chunks: {selectedDocument}
                    </Box>
                </DialogTitle>
                <DialogContent dividers>
                    {loadingChunks ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                            <CircularProgress />
                        </Box>
                    ) : (
                        <Box>
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                Total chunks: {chunks.length}
                            </Typography>
                            <Stack spacing={1}>
                                {chunks.map((chunk) => (
                                    <Accordion key={chunk.index}>
                                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                                                <Typography variant="subtitle2">
                                                    Chunk {chunk.index}
                                                </Typography>
                                                <Chip
                                                    label={`${chunk.char_count} chars`}
                                                    size="small"
                                                    variant="outlined"
                                                />
                                                <Chip
                                                    label={chunk.category}
                                                    size="small"
                                                    color="primary"
                                                    variant="outlined"
                                                />
                                            </Box>
                                        </AccordionSummary>
                                        <AccordionDetails>
                                            <Box>
                                                <Divider sx={{ mb: 2 }} />
                                                <Typography
                                                    variant="body2"
                                                    component="pre"
                                                    sx={{
                                                        whiteSpace: 'pre-wrap',
                                                        wordBreak: 'break-word',
                                                        fontFamily: 'monospace',
                                                        fontSize: '0.875rem',
                                                        backgroundColor: 'grey.50',
                                                        p: 2,
                                                        borderRadius: 1,
                                                        maxHeight: 400,
                                                        overflow: 'auto'
                                                    }}
                                                >
                                                    {chunk.content}
                                                </Typography>
                                                {chunk.uploaded_at && (
                                                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                                        Uploaded: {new Date(chunk.uploaded_at).toLocaleString()}
                                                    </Typography>
                                                )}
                                            </Box>
                                        </AccordionDetails>
                                    </Accordion>
                                ))}
                            </Stack>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setChunksDialogOpen(false)}>Close</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};

export default RAGManagement;
