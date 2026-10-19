import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import './Drawer.css';

export function Drawer({ isOpen, onClose, title, subtitle, children, width = 540 }) {
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    }
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="drawer-root">
          <motion.div
            className="drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
          />
          <motion.aside
            className="drawer-panel"
            style={{ width, maxWidth: '92vw' }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
          >
            <div className="drawer-header">
              <div className="drawer-title-group">
                <h3 id="drawer-title" className="drawer-title">
                  {title}
                </h3>
                {subtitle && <span className="drawer-subtitle text-muted">{subtitle}</span>}
              </div>
              <button
                type="button"
                className="drawer-close-btn"
                onClick={onClose}
                aria-label="Close panel"
              >
                <X size={16} />
              </button>
            </div>
            <div className="drawer-body">{children}</div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}
