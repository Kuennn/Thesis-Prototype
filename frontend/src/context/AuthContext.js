// src/context/AuthContext.js
// Global authentication state — wraps the whole app
// Stores JWT token in localStorage, provides login/logout functions

import React, { createContext, useContext, useState, useEffect } from 'react';
import BASE_URL, { apiFetch } from '../config';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token,       setToken]       = useState(localStorage.getItem('examcheck_token'));
  const [teacherName, setTeacherName] = useState(localStorage.getItem('examcheck_name') || '');
  const [loading,     setLoading]     = useState(true);

  // Verify token on mount
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    apiFetch(`${BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (!r.ok) throw new Error('Invalid token');
        return r.json();
      })
      .then(data => setTeacherName(data.name))
      .catch(() => {
        // Token expired or invalid — clear it
        localStorage.removeItem('examcheck_token');
        localStorage.removeItem('examcheck_name');
        setToken(null);
        setTeacherName('');
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const login = async (username, password) => {
    const form = new URLSearchParams();
    form.append('username', username);
    form.append('password', password);

    const res = await apiFetch(`${BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    localStorage.setItem('examcheck_token', data.access_token);
    localStorage.setItem('examcheck_name',  data.teacher_name);
    setToken(data.access_token);
    setTeacherName(data.teacher_name);
    return data;
  };

  const logout = () => {
    localStorage.removeItem('examcheck_token');
    localStorage.removeItem('examcheck_name');
    setToken(null);
    setTeacherName('');
  };

  return (
    <AuthContext.Provider value={{
      token, teacherName, loading,
      isAuthenticated: !!token,
      login, logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
