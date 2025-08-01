#!/usr/bin/env node

/**
 * Test script for MCP server reconnection on session errors
 * 
 * This script simulates a session error to test the reconnection logic
 */

import fetch from 'node-fetch';

const MCP_SERVER_URL = process.env.MCP_SERVER_URL || 'http://localhost:3001';

async function testReconnection() {
  console.log('🧪 Testing MCP Server Reconnection Logic');
  console.log('=====================================\n');

  try {
    // Step 1: Check server status
    console.log('1️⃣ Checking server status...');
    const statusResponse = await fetch(`${MCP_SERVER_URL}/status`);
    const status = await statusResponse.json();
    console.log('Server status:', JSON.stringify(status, null, 2));
    console.log('');

    // Step 2: Get available tools
    console.log('2️⃣ Getting available tools...');
    const infoResponse = await fetch(`${MCP_SERVER_URL}/info`);
    const info = await infoResponse.json();
    console.log(`Found ${info.toolCount} tools available`);
    
    // Find a personal-ai tool to test
    const personalAiTools = info.tools.filter(t => t.name.startsWith('personal_ai__'));
    if (personalAiTools.length > 0) {
      console.log(`Found ${personalAiTools.length} personal-ai tools`);
      console.log('');
      
      // Step 3: Try to call a tool (this might trigger a session error)
      const testTool = personalAiTools[0];
      console.log(`3️⃣ Testing tool: ${testTool.name}`);
      console.log(`Description: ${testTool.description}`);
      
      const toolCallBody = {
        jsonrpc: '2.0',
        id: 'test-reconnection',
        method: 'tools/call',
        params: {
          name: testTool.name,
          arguments: {}
        }
      };
      
      console.log('\nCalling tool...');
      const toolResponse = await fetch(`${MCP_SERVER_URL}/mcp`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(toolCallBody)
      });
      
      const toolResult = await toolResponse.json();
      console.log('Tool response:', JSON.stringify(toolResult, null, 2));
      
      if (toolResult.error) {
        console.log('\n⚠️  Tool call resulted in error:', toolResult.error.message);
        
        // Check if it was a session error
        if (toolResult.error.message.includes('session') || 
            toolResult.error.message.includes('Session')) {
          console.log('🔑 Session error detected - reconnection should have been triggered');
          
          // Wait a bit for reconnection to complete
          console.log('\n⏳ Waiting 5 seconds for reconnection to complete...');
          await new Promise(resolve => setTimeout(resolve, 5000));
          
          // Check status again to see if reconnection happened
          console.log('\n4️⃣ Checking server status after reconnection attempt...');
          const statusAfterResponse = await fetch(`${MCP_SERVER_URL}/status`);
          const statusAfter = await statusAfterResponse.json();
          
          const personalAiStatus = statusAfter.servers['personal-ai'];
          if (personalAiStatus) {
            console.log('\npersonal-ai server status:');
            console.log(`  Connected: ${personalAiStatus.connected}`);
            console.log(`  Reconnect attempts: ${personalAiStatus.reconnectAttempts}`);
            console.log(`  Last error: ${personalAiStatus.lastError || 'None'}`);
            
            if (personalAiStatus.connected) {
              console.log('\n✅ Reconnection successful!');
              
              // Try the tool call again
              console.log('\n5️⃣ Retrying tool call after reconnection...');
              const retryResponse = await fetch(`${MCP_SERVER_URL}/mcp`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json'
                },
                body: JSON.stringify(toolCallBody)
              });
              
              const retryResult = await retryResponse.json();
              console.log('Retry response:', JSON.stringify(retryResult, null, 2));
              
              if (!retryResult.error) {
                console.log('\n🎉 Tool call succeeded after reconnection!');
              } else {
                console.log('\n❌ Tool call still failing after reconnection');
              }
            } else {
              console.log('\n❌ Reconnection failed or still in progress');
            }
          }
        }
      } else {
        console.log('\n✅ Tool call succeeded without needing reconnection');
      }
      
    } else {
      console.log('⚠️  No personal-ai tools found. The personal-ai server might not be connected.');
    }

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
  }
}

// Run the test
testReconnection().catch(console.error);