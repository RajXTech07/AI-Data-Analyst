import React from 'react';

/**
 * Standard Button adhering to DESIGN.md Component Stylings:
 * - 10px rounded corners (rounded-btn)
 * - 44px tall (h-11)
 * - 600 font weight
 * - Signal Indigo primary with Deep Indigo hover
 * - Hairline border on secondary
 */
export const Button = ({
  variant = 'primary', // 'primary' | 'secondary' | 'text' | 'danger-text' | 'outline'
  size = 'md', // 'sm' | 'md' | 'lg'
  disabled = false,
  fullWidth = false,
  icon: Icon,
  iconPosition = 'left',
  children,
  className = '',
  onClick,
  type = 'button',
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-semibold transition-all duration-150 select-none focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2';

  const sizeStyles = {
    sm: 'h-8 px-3 text-xs rounded-lg gap-1.5',
    md: 'h-11 px-5 text-sm rounded-[10px] gap-2',
    lg: 'h-12 px-7 text-base rounded-[10px] gap-2.5',
  };

  const variants = {
    primary: disabled
      ? 'bg-primary-soft text-ink-muted cursor-not-allowed shadow-none'
      : 'bg-primary text-white hover:bg-primary-hover active:scale-[0.99] shadow-sm',
    secondary: disabled
      ? 'bg-canvas text-ink-muted border border-hairline cursor-not-allowed'
      : 'bg-surface text-ink-strong border border-hairline hover:bg-canvas active:bg-hairline shadow-xs',
    text: disabled
      ? 'text-ink-muted cursor-not-allowed'
      : 'text-primary hover:underline hover:text-primary-hover p-0 h-auto font-medium',
    'danger-text': disabled
      ? 'text-ink-muted cursor-not-allowed'
      : 'text-danger hover:underline hover:text-red-700 p-0 h-auto font-medium',
    outline: disabled
      ? 'text-ink-muted border border-hairline cursor-not-allowed'
      : 'border border-hairline text-ink hover:bg-canvas active:bg-hairline',
  };

  const widthStyle = fullWidth ? 'w-full' : '';

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${baseStyles} ${sizeStyles[size]} ${variants[variant]} ${widthStyle} ${className}`}
      {...props}
    >
      {Icon && iconPosition === 'left' && <Icon className="w-4 h-4 shrink-0" />}
      <span>{children}</span>
      {Icon && iconPosition === 'right' && <Icon className="w-4 h-4 shrink-0" />}
    </button>
  );
};

