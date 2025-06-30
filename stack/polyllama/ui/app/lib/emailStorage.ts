import { EmailSession, EmailSummary, EmailDraft } from '../types'

// Base storage interface for future persistence providers
export interface EmailStorageProvider {
  getSession(emailId: string): Promise<EmailSession | null>
  saveSession(session: EmailSession): Promise<void>
  updateSession(emailId: string, updates: Partial<EmailSession>): Promise<void>
  deleteSession(emailId: string): Promise<void>
  addSummary(emailId: string, summary: EmailSummary): Promise<void>
  addDraft(emailId: string, draft: EmailDraft): Promise<void>
  getSummaries(emailId: string): Promise<EmailSummary[]>
  getDrafts(emailId: string): Promise<EmailDraft[]>
}

// In-memory implementation (can be replaced with persistent storage later)
class InMemoryEmailStorage implements EmailStorageProvider {
  private sessions: Map<string, EmailSession> = new Map()

  async getSession(emailId: string): Promise<EmailSession | null> {
    return this.sessions.get(emailId) || null
  }

  async saveSession(session: EmailSession): Promise<void> {
    this.sessions.set(session.emailId, session)
  }

  async updateSession(emailId: string, updates: Partial<EmailSession>): Promise<void> {
    const session = this.sessions.get(emailId)
    if (session) {
      this.sessions.set(emailId, {
        ...session,
        ...updates,
        updatedAt: new Date().toISOString()
      })
    }
  }

  async deleteSession(emailId: string): Promise<void> {
    this.sessions.delete(emailId)
  }

  async addSummary(emailId: string, summary: EmailSummary): Promise<void> {
    let session = this.sessions.get(emailId)
    if (!session) {
      session = {
        id: `email-session-${Date.now()}`,
        emailId,
        summaries: [],
        drafts: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    }
    session.summaries.push(summary)
    session.updatedAt = new Date().toISOString()
    this.sessions.set(emailId, session)
  }

  async addDraft(emailId: string, draft: EmailDraft): Promise<void> {
    let session = this.sessions.get(emailId)
    if (!session) {
      session = {
        id: `email-session-${Date.now()}`,
        emailId,
        summaries: [],
        drafts: [],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    }
    session.drafts.push(draft)
    session.updatedAt = new Date().toISOString()
    this.sessions.set(emailId, session)
  }

  async getSummaries(emailId: string): Promise<EmailSummary[]> {
    const session = this.sessions.get(emailId)
    return session?.summaries || []
  }

  async getDrafts(emailId: string): Promise<EmailDraft[]> {
    const session = this.sessions.get(emailId)
    return session?.drafts || []
  }
}

// Export singleton instance
export const emailStorage = new InMemoryEmailStorage()

// Helper functions for email session management
export async function getOrCreateEmailSession(emailId: string): Promise<EmailSession> {
  let session = await emailStorage.getSession(emailId)
  if (!session) {
    session = {
      id: `email-session-${Date.now()}`,
      emailId,
      summaries: [],
      drafts: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    await emailStorage.saveSession(session)
  }
  return session
}

export async function saveEmailSummary(
  emailId: string,
  summary: string,
  keyTopics: string[],
  entities: EmailSummary['entities'],
  extractedFacts: string[],
  actionItems: string[],
  model: string
): Promise<EmailSummary> {
  const emailSummary: EmailSummary = {
    id: `summary-${Date.now()}`,
    emailId,
    summary,
    keyTopics,
    entities,
    extractedFacts,
    actionItems,
    createdAt: new Date().toISOString(),
    model
  }
  
  await emailStorage.addSummary(emailId, emailSummary)
  return emailSummary
}

export async function saveEmailDraft(
  emailId: string,
  replyType: EmailDraft['replyType'],
  subject: string,
  body: string,
  model: string
): Promise<EmailDraft> {
  const emailDraft: EmailDraft = {
    id: `draft-${Date.now()}`,
    emailId,
    replyType,
    subject,
    body,
    createdAt: new Date().toISOString(),
    model
  }
  
  await emailStorage.addDraft(emailId, emailDraft)
  return emailDraft
}