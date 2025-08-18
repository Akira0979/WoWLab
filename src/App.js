import React from 'react';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider, useMsal, useAccount } from '@azure/msal-react';

const msalConfig = {
  auth: {
    clientId: 'YOUR_AZURE_AD_CLIENT_ID',
    authority: 'https://login.microsoftonline.com/common',
    redirectUri: 'https://wowfactory.azurewebsites.net/loginnow'
  }
};

const msalInstance = new PublicClientApplication(msalConfig);

function SignInButton() {
  const { instance } = useMsal();
  function handleLogin() {
    instance.loginRedirect({ scopes: ["User.Read"] });
  }
  return <button onClick={handleLogin}>Sign In</button>;
}

function WelcomeUser() {
  const { accounts } = useMsal();
  const account = useAccount(accounts[0] || null);

  return account ? (
    <div>
      <h2>Welcome, {account.name}</h2>
      <p>Email: {account.username}</p>
    </div>
  ) : (
    <SignInButton />
  );
}

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <div style={ padding: "20px", fontFamily: "Verdana" }>
        <h1>WowFactory</h1>
        <WelcomeUser />
      </div>
    </MsalProvider>
  );
}

export default App;