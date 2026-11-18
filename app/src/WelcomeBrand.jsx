import React from 'react';
import './welcome.css';

export default function WelcomeBrand(){
 return <div className="welcome-brand" role="img" aria-label="Freedom GPT">
  <span className="welcome-brand-halo" aria-hidden="true"/>
  <span className="welcome-brand-word" aria-hidden="true"><span>Freedom</span><i/></span>
  <img className="welcome-brand-logo" src="/freedom.svg" alt="" aria-hidden="true"/>
  <span className="welcome-brand-spark" aria-hidden="true"/>
 </div>;
}
