'use client'

import { Instance, RunningModels } from '../types'
import FlowChart from './FlowChart'

interface SystemOverviewProps {
  instances: Instance[];
  instanceStatuses: Record<string, { status: string; name: string }>;
  runningModels: RunningModels;
  onRefresh: () => void;
}

export default function SystemOverview({ instances, instanceStatuses, runningModels, onRefresh }: SystemOverviewProps) {
  return (
    <FlowChart 
      instances={instances}
      instanceStatuses={instanceStatuses}
      runningModels={runningModels}
      onRefresh={onRefresh}
    />
  )
}