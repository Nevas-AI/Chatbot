import { format, formatDistanceToNow } from 'date-fns';

export function formatDate(iso: string): string {
  return format(new Date(iso), 'MMM d, yyyy h:mm a');
}

export function timeAgo(iso: string): string {
  return formatDistanceToNow(new Date(iso), { addSuffix: true });
}

export function clampText(text: string, max = 80): string {
  return text.length > max ? text.slice(0, max) + '…' : text;
}

export function statusColor(status: string): string {
  switch (status) {
    case 'active': return 'active';
    case 'escalated': return 'escalated';
    case 'ended': return 'ended';
    case 'pending': return 'pending';
    case 'assigned': return 'assigned';
    case 'resolved': return 'resolved';
    default: return 'ended';
  }
}
