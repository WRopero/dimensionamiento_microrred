#modelo paneles

def panel(area, irradiance, eficiencia, Npv, temperatura):
    """
    función que cálcula la producción del panel
    """
    p_pv_stc = 300
    G_stc = 1000
    alpha_p = -0.39
    t_cell = temperatura*irradiance*((45-20)/800)
    t_1 = 1 + (alpha_p/100)*(t_cell-25)
    fpv = 0.85
    Ppv = Npv*p_pv_stc*(irradiance/G_stc)*t_1*fpv

    return abs(Ppv)

def diesel(eficiencia, potencia, Ndg):
    """
    función que cálcula la producción del 
    generador diésel
    """
    Pdg = round(eficiencia*potencia*Ndg,4)
    
    return Pdg