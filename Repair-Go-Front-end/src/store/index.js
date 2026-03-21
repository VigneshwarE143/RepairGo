import { configureStore, createSlice } from '@reduxjs/toolkit';

// Auth Slice
const authSlice = createSlice({
  name: 'auth',
  initialState: {
    token: localStorage.getItem('token'),
    role: localStorage.getItem('role'),
    user: null,
    isAuthenticated: !!localStorage.getItem('token'),
  },
  reducers: {
    login: (state, action) => {
      const { token, role } = action.payload;
      state.token = token;
      state.role = role;
      state.isAuthenticated = true;
      localStorage.setItem('token', token);
      localStorage.setItem('role', role);
    },
    logout: (state) => {
      state.token = null;
      state.role = null;
      state.user = null;
      state.isAuthenticated = false;
      localStorage.removeItem('token');
      localStorage.removeItem('role');
    },
    setUser: (state, action) => {
      state.user = action.payload;
    },
  },
});

// UI Slice
const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    sidebarOpen: true,
    loading: false,
    notifications: [],
  },
  reducers: {
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setLoading: (state, action) => {
      state.loading = action.payload;
    },
    addNotification: (state, action) => {
      state.notifications.unshift({
        id: Date.now(),
        ...action.payload,
        read: false,
      });
    },
    markNotificationRead: (state, action) => {
      const notif = state.notifications.find((n) => n.id === action.payload);
      if (notif) notif.read = true;
    },
    clearNotifications: (state) => {
      state.notifications = [];
    },
  },
});

export const { login, logout, setUser } = authSlice.actions;
export const { toggleSidebar, setLoading, addNotification, markNotificationRead, clearNotifications } = uiSlice.actions;

const store = configureStore({
  reducer: {
    auth: authSlice.reducer,
    ui: uiSlice.reducer,
  },
});

export default store;
