#modelo paneles

def panel(area, irradiance, eficiencia, Npv):
    """
    función que cálcula la producción del panel
    """
    Ppv = round(eficiencia*Npv*area*irradiance,4)
    
    return Ppv

def diesel(eficiencia, potencia, Ndg):
    """
    función que cálcula la producción del 
    generador diésel
    """
    Pdg = round(eficiencia*potencia*Ndg,4)
    
    return Pdg