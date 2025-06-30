import { EmailMessage, EmailListResponse } from '../types'

export class GraphClient {
  private accessToken: string

  constructor(accessToken: string) {
    this.accessToken = accessToken
  }

  private async graphFetch(url: string, options: RequestInit = {}) {
    const response = await fetch(`https://graph.microsoft.com/v1.0${url}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`Graph API error: ${response.status} - ${error}`)
    }

    return response
  }

  async getEmails(
    pageSize: number = 10,
    pageToken?: string,
    filter?: string
  ): Promise<EmailListResponse> {
    let url = `/me/messages?$top=${pageSize}&$orderby=receivedDateTime desc`
    
    // Add fields selection to optimize response
    url += '&$select=id,conversationId,subject,bodyPreview,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments,importance,isRead,isDraft,webLink'
    
    if (filter) {
      url += `&$filter=${encodeURIComponent(filter)}`
    }
    
    if (pageToken) {
      url += `&$skiptoken=${pageToken}`
    }

    const response = await this.graphFetch(url)
    const data = await response.json()

    // Map Graph API response to our EmailMessage type
    const messages: EmailMessage[] = data.value.map((msg: any) => ({
      id: msg.id,
      conversationId: msg.conversationId,
      subject: msg.subject || '(No subject)',
      bodyPreview: msg.bodyPreview || '',
      from: msg.from,
      toRecipients: msg.toRecipients || [],
      ccRecipients: msg.ccRecipients || [],
      receivedDateTime: msg.receivedDateTime,
      hasAttachments: msg.hasAttachments || false,
      importance: msg.importance || 'normal',
      isRead: msg.isRead || false,
      isDraft: msg.isDraft || false,
      webLink: msg.webLink,
    }))

    // Extract next page token from @odata.nextLink
    let nextPageToken: string | undefined
    if (data['@odata.nextLink']) {
      const url = new URL(data['@odata.nextLink'])
      nextPageToken = url.searchParams.get('$skiptoken') || undefined
    }

    return {
      messages,
      nextPageToken,
      totalCount: data['@odata.count'],
    }
  }

  async getEmailById(emailId: string): Promise<EmailMessage> {
    const response = await this.graphFetch(`/me/messages/${emailId}`)
    const msg = await response.json()

    return {
      id: msg.id,
      conversationId: msg.conversationId,
      subject: msg.subject || '(No subject)',
      bodyPreview: msg.bodyPreview || '',
      body: msg.body,
      from: msg.from,
      toRecipients: msg.toRecipients || [],
      ccRecipients: msg.ccRecipients || [],
      receivedDateTime: msg.receivedDateTime,
      hasAttachments: msg.hasAttachments || false,
      importance: msg.importance || 'normal',
      isRead: msg.isRead || false,
      isDraft: msg.isDraft || false,
      webLink: msg.webLink,
      attachments: msg.attachments,
    }
  }

  async archiveEmail(emailId: string): Promise<void> {
    // Move to Archive folder
    await this.graphFetch(`/me/messages/${emailId}/move`, {
      method: 'POST',
      body: JSON.stringify({
        destinationId: 'archive'
      }),
    })
  }

  async deleteEmail(emailId: string): Promise<void> {
    await this.graphFetch(`/me/messages/${emailId}`, {
      method: 'DELETE',
    })
  }

  async markAsRead(emailId: string, isRead: boolean = true): Promise<void> {
    await this.graphFetch(`/me/messages/${emailId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        isRead,
      }),
    })
  }

  async sendEmail(
    to: string[],
    subject: string,
    body: string,
    replyToMessageId?: string,
    isReplyAll: boolean = false
  ): Promise<void> {
    if (replyToMessageId) {
      // Reply to existing message
      const endpoint = isReplyAll 
        ? `/me/messages/${replyToMessageId}/replyAll`
        : `/me/messages/${replyToMessageId}/reply`
      
      await this.graphFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          comment: body,
        }),
      })
    } else {
      // Send new message
      const message = {
        subject,
        body: {
          contentType: 'HTML',
          content: body,
        },
        toRecipients: to.map(email => ({
          emailAddress: { address: email }
        })),
      }

      await this.graphFetch('/me/sendMail', {
        method: 'POST',
        body: JSON.stringify({
          message,
          saveToSentItems: true,
        }),
      })
    }
  }

  async forwardEmail(
    messageId: string,
    to: string[],
    comment: string
  ): Promise<void> {
    await this.graphFetch(`/me/messages/${messageId}/forward`, {
      method: 'POST',
      body: JSON.stringify({
        comment,
        toRecipients: to.map(email => ({
          emailAddress: { address: email }
        })),
      }),
    })
  }

  // Batch operations for better performance
  async batchArchiveEmails(emailIds: string[]): Promise<void> {
    // Microsoft Graph batch endpoint supports up to 20 requests
    const batchSize = 20
    for (let i = 0; i < emailIds.length; i += batchSize) {
      const batch = emailIds.slice(i, i + batchSize)
      const requests = batch.map((id, index) => ({
        id: String(index),
        method: 'POST',
        url: `/me/messages/${id}/move`,
        body: { destinationId: 'archive' },
        headers: { 'Content-Type': 'application/json' }
      }))

      await this.graphFetch('/$batch', {
        method: 'POST',
        body: JSON.stringify({ requests }),
      })
    }
  }

  async batchDeleteEmails(emailIds: string[]): Promise<void> {
    const batchSize = 20
    for (let i = 0; i < emailIds.length; i += batchSize) {
      const batch = emailIds.slice(i, i + batchSize)
      const requests = batch.map((id, index) => ({
        id: String(index),
        method: 'DELETE',
        url: `/me/messages/${id}`,
      }))

      await this.graphFetch('/$batch', {
        method: 'POST',
        body: JSON.stringify({ requests }),
      })
    }
  }
}