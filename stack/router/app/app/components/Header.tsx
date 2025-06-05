'use client'

import { useCallback } from 'react'
import styles from './Header.module.css'

interface HeaderProps {
  onRefresh: () => void;
}

export default function Header({ onRefresh }: HeaderProps) {
  const handleRefresh = useCallback(() => {
    const icon = document.querySelector(`.${styles.refreshIcon}`)
    if (icon) {
      icon.classList.add(styles.spinning)
      setTimeout(() => {
        icon.classList.remove(styles.spinning)
      }, 1000)
    }
    onRefresh()
  }, [onRefresh])

  return (
    <header className={styles.header}>
      <div className={styles.content}>
        <div className={styles.logo}>
          <div className={styles.logoIcon}>🦙</div>
          <span>PolyLlama</span>
        </div>
        <div className={styles.actions}>
          <button className={styles.refreshBtn} onClick={handleRefresh}>
            <span className={styles.refreshIcon}>↻</span>
            <span>Refresh</span>
          </button>
        </div>
      </div>
    </header>
  )
}