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
      maxWidth: '800px',
      margin: '2rem auto',
      padding: '0 2rem'
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
              flex: 1
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                backgroundColor: isCompleted ? '#28a745' : isActive ? '#007bff' : '#e9ecef',
                color: isCompleted || isActive ? 'white' : '#666',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                fontSize: '1rem',
                marginBottom: '0.5rem',
                transition: 'all 0.3s ease'
              }}>
                {isCompleted ? '✓' : stepNumber}
              </div>
              <span style={{
                fontSize: '0.9rem',
                color: isActive ? '#007bff' : '#666',
                fontWeight: isActive ? '600' : '400',
                textAlign: 'center'
              }}>
                {step}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div style={{
                flex: 1,
                height: '2px',
                backgroundColor: isCompleted ? '#28a745' : '#e9ecef',
                margin: '0 1rem',
                marginTop: '-20px',
                transition: 'all 0.3s ease'
              }} />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

