import axios from 'axios';

// Prefer env override, fall back to local 8000 where FastAPI is running
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      window.location.href = '/login';
    }
    return Promise.reject(new Error(message));
  }
);

// ============================================================================
// Authentication API
// ============================================================================
export const authAPI = {
  register: (data) => api.post('/register', data),
  login: (data) => api.post('/login', data),
  registerTechnician: (data) => api.post('/register-technician', data),
};

// ============================================================================
// Service Requests API (Customer)
// ============================================================================
export const serviceAPI = {
  create: (data) => api.post('/services', data),
  estimate: (data) => api.post('/services/estimate', data),
  getMyRequests: () => api.get('/services/my'),
  getSuggestedTechnicians: (serviceId) => api.get(`/services/${serviceId}/suggested-technicians`),
  rate: (serviceId, data) => api.post(`/services/${serviceId}/rate`, data),
  pay: (serviceId, data) => api.post(`/services/${serviceId}/pay`, data),
  updateStatus: (serviceId, data) => api.patch(`/services/${serviceId}/status`, data),
  
  // New booking flow: customer chooses from top 3 suggested technicians
  chooseTechnician: (serviceId, data) => api.post(`/services/${serviceId}/choose-technician`, data),
  
  // Legacy: Confirm booking with ML-recommended technician (picks top 1 automatically)
  confirmBooking: (serviceId) => api.post(`/services/${serviceId}/confirm-booking`),
  
  // Cancel with reason
  getCancellationReasons: () => api.get('/services/cancellation-reasons'),
  cancel: (serviceId, data) => api.post(`/services/${serviceId}/cancel`, data),
  
  // Live tracking
  getTechnicianLocation: (serviceId) => api.get(`/services/${serviceId}/technician-location`),
};

// ============================================================================
// Technician API
// ============================================================================
export const technicianAPI = {
  updateLocation: (data) => api.patch('/technicians/location', data),
  getProfile: () => api.get('/technicians/me'),
  getMyJobs: () => api.get('/technicians/my-jobs'),
  
  // Job acceptance/rejection
  getPendingJobs: () => api.get('/technicians/pending-jobs'),
  respondToJob: (serviceId, data) => api.post(`/services/${serviceId}/respond`, data),
  
  // New flow: technician accepts/rejects from choose-technician flow
  respondToRequest: (serviceId, data) => api.patch(`/services/${serviceId}/technician-response`, data),
  
  // Live location tracking (Ola/Rapido style)
  updateLiveLocation: (data) => api.patch('/technicians/live-location', data),
  startNavigation: (serviceId) => api.post(`/technicians/start-navigation/${serviceId}`),
  arrive: (serviceId) => api.post(`/technicians/arrive/${serviceId}`),
  complete: (serviceId) => api.post(`/technicians/complete/${serviceId}`),
  
  // Availability
  updateAvailability: (data) => api.patch('/technicians/availability', data),
};

// ============================================================================
// Admin API
// ============================================================================
export const adminAPI = {
  // Users
  getUsers: () => api.get('/admin/users'),
  deactivateUser: (userId) => api.patch(`/admin/users/${userId}/deactivate`),
  reactivateUser: (userId) => api.patch(`/admin/users/${userId}/reactivate`),
  getDeactivatedUsers: () => api.get('/admin/deactivated/users'),
  
  // Technicians
  getTechnicians: () => api.get('/admin/technicians'),
  deactivateTechnician: (techId) => api.patch(`/admin/technicians/${techId}/deactivate`),
  reactivateTechnician: (techId) => api.patch(`/admin/technicians/${techId}/reactivate`),
  getDeactivatedTechnicians: () => api.get('/admin/deactivated/technicians'),
  
  // Jobs/Services
  getJobs: () => api.get('/admin/jobs'),
  getRequests: () => api.get('/admin/requests'),
  assignTechnician: (serviceId) => api.post(`/services/${serviceId}/assign`),
  reassignStale: () => api.post('/admin/reassign-stale'),
  processRefund: (serviceId, data) => api.post(`/services/${serviceId}/refund`, data),
  
  // Revenue
  getRevenue: () => api.get('/admin/revenue'),
  
  // Categories
  getCategories: () => api.get('/admin/categories'),
  upsertCategory: (data) => api.post('/admin/categories', data),
  updateCategory: (id, data) => api.post('/admin/categories', data), // Upsert handles updates
  deleteCategory: (id) => api.delete(`/admin/categories/${id}`),
  
  // Fraud
  fraudCheck: () => api.post('/admin/fraud/check'),
  
  // Cache
  getCacheStats: () => api.get('/admin/cache/stats'),
  clearCache: () => api.post('/admin/cache/clear'),
  
  // Background Jobs
  getBackgroundJobHealth: () => api.get('/admin/health/background-jobs'),
};

// ============================================================================
// ML (Machine Learning) API
// ============================================================================
export const mlAPI = {
  // Reliability Model
  predictReliability: (data) => api.post('/ml/predict-reliability', data),
  getModelStatus: () => api.get('/ml/model-status'),
  trainModel: (data) => api.post('/ml/train', data),
  reloadModel: () => api.post('/ml/reload-model'),
  trainAndReload: (data) => api.post('/ml/train-and-reload', data),
  
  // Demand Model
  predictDemand: (data) => api.post('/ml/predict-demand', data),
  getDemandModelStatus: () => api.get('/ml/demand-model-status'),
  trainDemand: (data) => api.post('/ml/train-demand', data),
  reloadDemandModel: () => api.post('/ml/reload-demand-model'),
  trainDemandAndReload: (data) => api.post('/ml/train-demand-and-reload', data),
  clearDemandCache: () => api.post('/ml/clear-demand-cache'),
  getDemandForecast: (hours = 24) => api.get(`/ml/demand-forecast?hours=${hours}`),
  
  // Fraud Model
  getFraudScore: (entityType, entityId, store = false) => 
    api.get(`/ml/fraud-score/${entityType}/${entityId}?store_result=${store}`),
  getFraudModelStatus: () => api.get('/ml/fraud-model-status'),
  trainFraud: (data) => api.post('/ml/train-fraud', data),
  reloadFraudModel: () => api.post('/ml/reload-fraud-model'),
  trainFraudAndReload: (data) => api.post('/ml/train-fraud-and-reload', data),
  fraudScan: () => api.post('/ml/fraud-scan'),
  getFraudFlags: (status, entityType) => {
    let url = '/ml/fraud-flags';
    const params = [];
    if (status) params.push(`status=${status}`);
    if (entityType) params.push(`entity_type=${entityType}`);
    if (params.length) url += '?' + params.join('&');
    return api.get(url);
  },
  updateFraudFlagStatus: (entityId, status) => 
    api.patch(`/ml/fraud-flags/${entityId}/status?status=${status}`),
  
  // Model Registry
  getAllModelsStatus: () => api.get('/ml/models'),
  getModelHistory: (modelName, limit = 10) => 
    api.get(`/ml/models/${modelName}/history?limit=${limit}`),
  getActiveModel: (modelName) => api.get(`/ml/models/${modelName}/active`),
  deployModel: (modelName, version) => {
    let url = `/ml/models/${modelName}/deploy`;
    if (version) url += `?version=${version}`;
    return api.post(url);
  },
};

// ============================================================================
// WebSocket Service (optional - fails gracefully)
// ============================================================================
export const createWebSocket = (userId, onMessage) => {
  try {
    const token = localStorage.getItem('token');
    const wsBase = API_URL.replace(/^http/, 'ws');
    const url = `${wsBase}/ws/notifications/${userId}${token ? `?token=${token}` : ''}`;
    const ws = new WebSocket(url);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        // Ignore parse errors
      }
    };
    
    ws.onerror = () => {
      // WebSocket is optional - fail silently
    };

    ws.onclose = () => {
      // Connection closed - no action needed
    };
    
    return ws;
  } catch (e) {
    // Return a mock WebSocket object if creation fails
    return { close: () => {}, readyState: 3 };
  }
};

export default api;
