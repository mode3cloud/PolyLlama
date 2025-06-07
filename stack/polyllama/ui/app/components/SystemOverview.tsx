'use client'

import { Instance, RunningModels } from '../types'
import FlowChart from './FlowChart'

interface SystemOverviewProps {
  instances: Instance[];
  instanceStatuses: Record<string, any>;
  runningModels: RunningModels;
  modelContexts: Record<string, number>;
  onRefresh: () => void;
}

export default function SystemOverview({ instances, instanceStatuses, runningModels, modelContexts, onRefresh }: SystemOverviewProps) {
  return (
    <FlowChart 
      instances={instances}
      instanceStatuses={instanceStatuses}
      runningModels={runningModels}
      modelContexts={modelContexts}
      onRefresh={onRefresh}
    />
  )
}