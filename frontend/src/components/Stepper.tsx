import React from 'react'

interface StepperProps {
  currentStep: number
  steps: string[]
}

export const Stepper: React.FC<StepperProps> = ({ currentStep, steps }) => {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      maxWidth: '900px',
      margin: '2rem auto',
      padding: '0 2rem',
      position: 'relative'
    }}>
      {steps.map((step, index) => {
        const stepNumber = index + 1
        const isActive = stepNumber === currentStep
        const isCompleted = stepNumber < currentStep
        
        return (
          <React.Fragment key={index}>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              flex: 1,
              position: 'relative',
              zIndex: 2
            }}>
              <div style={{
                width: '50px',
                height: '50px',
                borderRadius: '50%',
                backgroundColor: isCompleted 
                  ? '#10b981' 
                  : isActive 
                    ? 'rgba(255,255,255,0.95)' 
                    : 'rgba(255,255,255,0.3)',
                color: isCompleted 
                  ? 'white' 
                  : isActive 
                    ? '#6366f1' 
                    : 'rgba(255,255,255,0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                fontSize: '1.1rem',
                marginBottom: '0.75rem',
                transition: 'all 0.3s ease',
                boxShadow: isActive 
                  ? '0 4px 12px rgba(99,102,241,0.4)' 
                  : isCompleted 
                    ? '0 2px 8px rgba(16,185,129,0.3)' 
                    : '0 2px 4px rgba(0,0,0,0.1)',
                border: isActive ? '3px solid rgba(255,255,255,0.5)' : 'none',
                transform: isActive ? 'scale(1.1)' : 'scale(1)'
              }}>
                {isCompleted ? '✓' : stepNumber}
              </div>
              <span style={{
                fontSize: '0.95rem',
                color: isActive ? 'white' : 'rgba(255,255,255,0.8)',
                fontWeight: isActive ? '600' : '400',
                textAlign: 'center',
                textShadow: '0 1px 3px rgba(0,0,0,0.2)',
                transition: 'all 0.3s ease'
              }}>
                {step}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div style={{
                flex: 1,
                height: '3px',
                backgroundColor: isCompleted 
                  ? 'rgba(16,185,129,0.6)' 
                  : 'rgba(255,255,255,0.3)',
                margin: '0 1rem',
                marginTop: '-25px',
                transition: 'all 0.3s ease',
                borderRadius: '2px',
                boxShadow: isCompleted 
                  ? '0 1px 3px rgba(16,185,129,0.2)' 
                  : 'none'
              }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

