import { useState, useEffect, useCallback } from 'react'
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import toast from 'react-hot-toast'

import { getRiskAnalysis, getAllData, simulateAttack, getCostImpact } from '../api/client'

const getLayoutedElements = (nodes, edges, direction = 'TB') => {
  // ✅ Create a fresh graph every call — fixes stale node positions when data changes
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const isHorizontal = direction === 'LR'
  dagreGraph.setGraph({ rankdir: direction })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 230, height: 92 })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - 230 / 2,
        y: nodeWithPosition.y - 92 / 2,
      },
    }
  })

  return { nodes: newNodes, edges }
}

const levelColor = {
  High: '#f87171',   // Red
  Medium: '#fbbf24', // Yellow
  Low: '#34d399',    // Green
}

const levelSurface = {
  High: 'linear-gradient(135deg, #fff7f7, #ffe4e9)',
  Medium: 'linear-gradient(135deg, #fff9e8, #fff1c2)',
  Low: 'linear-gradient(135deg, #f0fdf4, #d9fbe8)',
}

const buildNodeStyle = (riskLevel) => ({
  background: levelSurface[riskLevel] || '#f8fafc',
  color: '#0f172a',
  border: `3px solid ${levelColor[riskLevel] || '#64748b'}`,
  borderRadius: '10px',
  boxShadow: `0 10px 24px ${levelColor[riskLevel] || '#64748b'}33`,
  width: 230,
  minHeight: 92,
  padding: 0,
})

function NodeLabel({ node }) {
  return (
    <div className="graph-node-label">
      <div className="graph-node-topline">
        <span className={`graph-risk-dot graph-risk-${node.risk_level?.toLowerCase()}`} />
        <span>{node.risk_level} Risk</span>
      </div>
      <div className="graph-node-name">{node.name}</div>
      <div className="graph-node-meta">
        <span>{node.resource_uid}</span>
        <span>{node.resource_type}</span>
      </div>
      <div className="graph-node-score">Score {Number(node.risk_score).toFixed(1)}</div>
    </div>
  )
}

export default function GraphDashboard() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const [stats, setStats] = useState({ total_nodes: 0, high_risk: 0, total_cost: 0 })
  const [selectedNode, setSelectedNode] = useState(null)

  // Simulation state
  const [simulating, setSimulating] = useState(false)
  const [attackSteps, setAttackSteps] = useState([])
  const [currentStep, setCurrentStep] = useState(-1)
  const [attackedNodes, setAttackedNodes] = useState(new Set())
  const [costImpactData, setCostImpactData] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [riskRes, dataRes] = await Promise.all([
        getRiskAnalysis(),
        getAllData(),
      ])

      const riskNodes = riskRes.data.nodes || []
      const connections = dataRes.data.connections || []

      // Calculate stats
      let totalCost = 0
      let highRiskCount = 0
      
      const rfNodes = riskNodes.map((n) => {
        totalCost += Number(n.cost || 0)
        if (n.risk_level === 'High') highRiskCount++
        
        return {
          id: n.resource_uid,
          data: {
            label: <NodeLabel node={n} />,
            fullData: n,
          },
          style: buildNodeStyle(n.risk_level),
        }
      })

      const rfEdges = connections.map((c) => ({
        id: `e-${c.id}`,
        source: c.from_node,
        target: c.to_node,
        animated: true,
        label: c.connection_type,
        style: { stroke: '#8bb7e8', strokeWidth: 2.2 },
        labelStyle: { fill: '#ffffff', fontWeight: 800, fontSize: 12 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.9 },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 6,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#8bb7e8',
        },
      }))

      setStats({
        total_nodes: riskNodes.length,
        high_risk: highRiskCount,
        total_cost: totalCost,
      })

      const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
        rfNodes,
        rfEdges
      )

      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    } catch (err) {
      console.error(err)
      setError('Failed to fetch graph data. Make sure backend is running.')
    } finally {
      setLoading(false)
    }
  }, [setNodes, setEdges])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Process simulation steps
  useEffect(() => {
    let timer
    if (simulating && currentStep < attackSteps.length) {
      timer = setTimeout(() => {
        setAttackedNodes((prev) => {
          const newSet = new Set(prev)
          const currentNodes = attackSteps[currentStep] || []
          currentNodes.forEach(n => newSet.add(n))
          return newSet
        })
        setCurrentStep((s) => s + 1)
      }, 1000)

    } else if (simulating && currentStep >= attackSteps.length) {
      setSimulating(false)
      toast.success('Attack simulation complete!')
      
      // Fetch cost impact automatically when simulation finishes
      if (selectedNode) {
        getCostImpact(selectedNode.resource_uid).then(res => {
          setCostImpactData(res.data)
        }).catch(console.error)
      }
    }
    return () => clearTimeout(timer)
  }, [simulating, currentStep, attackSteps, selectedNode])

  // Update node styles based on attacked status
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        if (attackedNodes.has(n.id)) {
          return {
            ...n,
          style: {
              ...buildNodeStyle(n.data.fullData.risk_level),
              background: 'linear-gradient(135deg, #ffe4e6, #fecdd3)',
              border: '3px solid #e11d48',
              boxShadow: '0 0 24px rgba(225,29,72,0.55)',
              transition: 'all 0.5s ease',
            },
          }
        }
        return n
      })
    )
  }, [attackedNodes, setNodes])

  const handleStartSimulation = async () => {
    if (!selectedNode) {
      toast.error('Please select a starting node for the simulation.')
      return
    }

    try {
      const res = await simulateAttack(selectedNode.resource_uid)
      
      // Reset state for new simulation
      setAttackedNodes(new Set())
      
      // Reset styles manually immediately 
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          style: {
            ...buildNodeStyle(n.data.fullData.risk_level),
          }
        }))
      )

      setAttackSteps(res.data.steps)
      setCurrentStep(0)
      setSimulating(true)
      toast.success(`Starting simulation from ${selectedNode.name}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start simulation')
    }
  }

  const handleResetSimulation = () => {
    setSimulating(false)
    setAttackSteps([])
    setCurrentStep(-1)
    setAttackedNodes(new Set())
    
    // Reset nodes styles
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        style: {
          ...buildNodeStyle(n.data.fullData.risk_level),
        }
      }))
    )
  }

  const onNodeClick = (event, node) => {
    setSelectedNode(node.data.fullData)
  }

  if (loading) return (
    <div className="loading-center">
      <div className="spinner" />
      <span>Loading graph...</span>
    </div>
  )

  if (error) return (
    <div className="empty-state">
      <div className="empty-icon">⚠️</div>
      <p style={{ color: 'var(--rose)' }}>{error}</p>
      <button className="btn btn-secondary btn-sm" onClick={fetchData}>Retry</button>
    </div>
  )

  if (nodes.length === 0) return (
    <div className="empty-state">
      <div className="empty-icon">+</div>
      <p>No graph data yet. Add resources and connections first, then refresh the dashboard.</p>
      <button className="btn btn-secondary btn-sm" onClick={fetchData}>Refresh</button>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div className="page-header" style={{ marginBottom: '0' }}>
        <h1>Visualization Dashboard</h1>
        <p>Interactive graph of your cloud infrastructure with real-time risk coding and attack simulations.</p>
      </div>

      {/* ── Summary Stats ──────────────────────────────── */}
      <div className="grid-3" style={{ marginBottom: '0.5rem' }}>
        <div className="stat-card">
          <span className="stat-label">Total Nodes</span>
          <span className="stat-value" style={{ color: 'var(--cyan)' }}>{stats.total_nodes}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">🔴 High Risk</span>
          <span className="stat-value" style={{ color: 'var(--rose)' }}>{stats.high_risk}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Cost Impact</span>
          <span className="stat-value" style={{ color: 'var(--amber)' }}>
            ${stats.total_cost.toFixed(2)}
          </span>
        </div>
      </div>

      {/* ── Main Area (Graph + Side Panel) ──────────────── */}
      <div className="graph-layout">
        
        {/* React Flow Graph */}
        <div className="graph-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            fitViewOptions={{ padding: 0.18 }}
          >
            <Controls />
            <MiniMap 
              nodeColor={(node) => attackedNodes.has(node.id) ? 'var(--rose)' : (levelColor[node.data.fullData.risk_level] || '#ccc')} 
              style={{ backgroundColor: 'var(--bg-surface)' }}
            />
            <Background color="var(--graph-grid)" gap={18} />
          </ReactFlow>
        </div>

        {/* Side Panel */}
        <div className="sticky-panel">
          
          {/* Attack Simulation Panel */}
          <div className="card" style={{ flex: '0 0 auto' }}>
            <div className="card-title">Attack Simulation</div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Select a start node on the graph, then hit "Start Simulation" to visualize a BFS-based attack spread.
            </p>
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: costImpactData ? '1rem' : 0 }}>
              <button 
                className="btn btn-primary" 
                onClick={handleStartSimulation}
                disabled={simulating || !selectedNode}
                style={{ flex: 1 }}
              >
                {simulating ? 'Simulating...' : 'Start Simulation'}
              </button>
              {(attackSteps.length > 0 || attackedNodes.size > 0) && (
                <button 
                  className="btn btn-secondary" 
                  onClick={handleResetSimulation}
                >
                  Reset
                </button>
              )}
            </div>

            {costImpactData && !simulating && (
              <div style={{ 
                marginTop: '1rem', 
                padding: '1rem', 
                background: 'rgba(251,191,36,0.1)', 
                border: '1px solid rgba(251,191,36,0.3)',
                borderRadius: '8px'
              }}>
                <h4 style={{ color: 'var(--amber)', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Simulation Results</h4>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Nodes Compromised:</span>
                  <span style={{ color: 'var(--rose)', fontWeight: 'bold' }}>{costImpactData.total_impacted_nodes}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Total Cost Loss:</span>
                  <span style={{ color: 'var(--amber)', fontWeight: 'bold' }}>${Number(costImpactData.total_cost_loss).toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          <div className="card" style={{ flex: 1 }}>
            <div className="card-title">Node Details</div>
            
            {selectedNode ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.2rem', color: 'var(--cyan)' }}>{selectedNode.name}</h3>
                  <code className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{selectedNode.resource_uid}</code>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className="badge badge-cyan">{selectedNode.resource_type}</span>
                  <span className={`badge ${selectedNode.risk_level === 'High' ? 'badge-rose' : selectedNode.risk_level === 'Medium' ? 'badge-amber' : 'badge-emerald'}`}>
                    {selectedNode.risk_level} Risk ({selectedNode.risk_score} pts)
                  </span>
                  <span className={`badge ${selectedNode.public_access ? 'badge-rose' : 'badge-emerald'}`}>
                    {selectedNode.public_access ? 'Public' : 'Private'}
                  </span>
                </div>

                <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <div style={{ marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Provider / Region</span>
                    <div style={{ color: 'var(--text-primary)' }}>{selectedNode.provider} • {selectedNode.region}</div>
                  </div>

                  <div style={{ marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Monthly Cost</span>
                    <div style={{ color: 'var(--amber)', fontSize: '1.1rem', fontWeight: 'bold' }}>
                      ${Number(selectedNode.cost).toFixed(2)}
                    </div>
                  </div>

                  <div style={{ marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Connections (In+Out)</span>
                    <div style={{ color: 'var(--violet)', fontFamily: 'JetBrains Mono, monospace' }}>
                      {selectedNode.connectivity}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-state" style={{ padding: '2rem 1rem' }}>
                <div className="empty-icon" style={{ fontSize: '2rem' }}>🖱️</div>
                <p>Click on a node in the graph to view its detailed risk and cost impact.</p>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}
