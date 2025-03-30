"""
Module: message_integration.py
---------------------------
Intégration du système de messagerie dans la simulation STS.

Montre comment intégrer le broker de messages dans la simulation
existante pour faciliter la communication entre composants.

Classes:
    MessageSimulationManager: Extension du SimulationManager avec messagerie

"""

import logging
import time
from typing import Dict, List, Set
from threading import Event

from src.seed.stsseed import STSSeed
from src.projects.project_0.simulations.simulation_manager import SimulationManager
from src.projects.project_2.core.message_broker import MessageBroker, MessageType, Message
from src.projects.project_2.core.message_components import MessageBusAdapter, MessageStopAdapter


class MessageSimulationManager:
    """Gestionnaire de simulation utilisant le système de messagerie"""
    
    def __init__(self, seed: STSSeed, duration: int = 60):
        """
        Initialise le gestionnaire de simulation
        
        Args:
            seed: Instance de STSSeed avec les données du réseau
            duration: Durée de la simulation en secondes
        """
        self.seed = seed
        self.duration = duration
        self.stop_event = Event()
        self.logger = logging.getLogger("message_simulation")
        
        # Initialisation du broker de messages
        self.message_broker = MessageBroker()
        
        # Adaptateurs pour les composants
        self.bus_adapters: Dict[int, MessageBusAdapter] = {}
        self.stop_adapters: Dict[str, MessageStopAdapter] = {}
        
        # Gestionnaire de simulation standard
        self.base_simulation = SimulationManager(seed, duration)
    
    def initialize(self) -> bool:
        """
        Initialise la simulation avec le système de messagerie
        
        Returns:
            bool: True si l'initialisation est réussie, False sinon
        """
        try:
            self.logger.info("Initialisation de la simulation avec messagerie...")
            
            # Création des adaptateurs pour les bus
            for bus_id, bus in self.seed.buses.items():
                self.bus_adapters[bus_id] = MessageBusAdapter(bus)
                self.logger.info(f"Adaptateur créé pour Bus-{bus_id}")
            
            # Création des adaptateurs pour les arrêts
            for stop_name, stop in self.seed.stops.items():
                self.stop_adapters[stop_name] = MessageStopAdapter(stop)
                self.logger.info(f"Adaptateur créé pour Stop-{stop_name}")
            
            # Publier un message de démarrage système
            self.publish_system_alert("Démarrage du système", level="INFO", 
                                     details={"component_count": len(self.bus_adapters) + len(self.stop_adapters)})
            
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation: {e}")
            return False
    
    def start_simulation(self) -> bool:
        """
        Démarre la simulation
        
        Returns:
            bool: True si le démarrage est réussi, False sinon
        """
        try:
            # Initialiser le système de messagerie
            if not self.initialize():
                return False
            
            # Démarrer la simulation de base
            self.base_simulation.start_simulation()
            
            # Démarrer le générateur de messages pour le scénario 0
            self.start_message_generator_scenario_0()
            
            # Démarrer le générateur de messages pour le scénario 1
            self.start_message_generator_scenario_1()
            
            # Démarrer le générateur de messages pour le scénario 2
            self.start_message_generator_scenario_2()
            
            # Démarrer le générateur de messages pour le scénario 3
            self.start_message_generator_scenario_3()
            
            # Démarrer le générateur de messages pour le scénario 4
            self.start_message_generator_scenario_4()
            
            # Démarrer le générateur de messages pour le scénario 5
            self.start_message_generator_scenario_5()
            
            
            # Log du démarrage
            self.logger.info("Simulation avec messagerie démarrée")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur au démarrage: {e}")
            return False
    
    def stop_simulation(self) -> None:
        """Arrête la simulation et nettoie les ressources"""
        try:
            # Publier un message d'arrêt
            self.publish_system_alert("Arrêt du système", level="INFO")
            
            # Arrêter la simulation de base
            self.base_simulation.stop_simulation()
            
            # Arrêter le broker de messages
            self.message_broker.shutdown()
            
            self.logger.info("Simulation avec messagerie arrêtée")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt: {e}")
    
    def publish_system_alert(self, message: str, level: str = "INFO", details: Dict = None) -> None:
        """
        Publie une alerte système
        
        Args:
            message: Texte de l'alerte
            level: Niveau d'alerte (INFO, WARNING, ERROR)
            details: Détails additionnels
        """
        system_message = Message(
            MessageType.SYSTEM_ALERT,
            "SystemManager",
            {
                'message': message,
                'level': level,
                'details': details or {}
            }
        )
        self.message_broker.publish(system_message)
    
    @staticmethod
    def run(duration: int = 60) -> bool:
        """
        Lance une simulation complète avec messagerie
        
        Args:
            duration: Durée de la simulation en secondes
            
        Returns:
            bool: True si la simulation s'est correctement exécutée
        """
        # Initialisation du système
        seed = STSSeed()
        if not seed.initialize_system():
            logging.error("Échec de l'initialisation du système")
            return False
        
        # Création du gestionnaire de simulation
        simulation = MessageSimulationManager(seed, duration)
        
        try:
            # Démarrage de la simulation
            if not simulation.start_simulation():
                return False
            
            # Attente pendant la durée spécifiée
            logging.info(f"Simulation en cours pour {duration} secondes...")
            start_time = time.time()
            while (time.time() - start_time) < duration and not simulation.stop_event.is_set():
                time.sleep(1)
                
            # Succès
            return True
            
        except KeyboardInterrupt:
            logging.warning("Simulation interrompue par l'utilisateur")
            return False
            
        finally:
            # Nettoyage
            simulation.stop_simulation()

    
    def start_message_generator_scenario_0(self):
        """Démarre un thread qui génère des messages de test périodiquement"""
        import threading
        import time
        import random
        
        def generate_messages():
            """Génère différents types de messages pour tester le système"""
            self.logger.info("Démarrage du générateur de messages de test pour la STS")
            
            while not self.stop_event.is_set():
                try:
                    # Exemple de messages de mise à jour de route
                    if self.seed.routes and len(self.seed.routes) > 0:
                        route_id = list(self.seed.routes.keys())[0]  # Utiliser la première route disponible
                        self.message_broker.publish(Message(
                            MessageType.ROUTE_UPDATE,
                            "STSMessageGenerator",
                            {
                                'bus_id': 0,  # bus = 0 du système (Je laisse le choix de mettre ce que vous voulez)
                                'route_id': route_id
                            }
                        ))
                        self.logger.info(f"Message de test envoyé: ROUTE_UPDATE pour bus 0, route {route_id}")
                    
                    # Exemple de messages de mise à jour d'horaire
                    self.message_broker.publish(Message(
                        MessageType.SCHEDULE_UPDATE,
                        "STSMessageGenerator",
                        {
                            'bus_id': 0,
                            'schedule_updates': {
                                'S0': {'arrival': time.time(), 'departure': time.time() + 300}
                            }
                        }
                    ))
                    self.logger.info("Message de test envoyé: SCHEDULE_UPDATE")
                    
                    # Exemple de messages de mise à jour de statut d'arrêt
                    self.message_broker.publish(Message(
                        MessageType.STOP_STATUS,
                        "STSMessageGenerator",
                        {
                            'stop_id': 0,
                            'is_occupied': True,
                            'waiting_passengers': 5,
                            'current_buses': [0, 1]
                        }
                    ))
                    self.logger.info("Message de test envoyé: STOP_STATUS")
                    
                    # Exemple de messages de mise à jour de capacité
                    self.message_broker.publish(Message(
                        MessageType.CAPACITY_UPDATE,
                        "STSMessageGenerator",
                        {
                            'bus_id': 0,
                            'total_capacity': 30,
                            'available_seats': 15,
                            'passenger_count': 15
                        }
                    ))
                    self.logger.info("Message de test envoyé: CAPACITY_UPDATE")
                    
                    # Exemple de messages de confirmation d'alighting
                    self.message_broker.publish(Message(
                        MessageType.PASSENGER_ALIGHTING,
                        "STSMessageGenerator",
                        {
                            'passenger_id': 0,
                            'bus_id': 0,
                            'stop_id': 0,
                            'status': 'confirmed'
                        }
                    ))
                    self.logger.info("Message de test envoyé: PASSENGER_ALIGHTING")
                    
                    # Attendre entre chaque série de messages
                    time.sleep(5)
                    
                except Exception as e:
                    self.logger.error(f"Erreur dans le générateur de messages: {e}")
                    time.sleep(10)  # Plus long délai en cas d'erreur Attention impourtant sinon il y a plusieurs erreurs.
        
        # Créer et démarrer le thread de génération
        generator_thread = threading.Thread(
            target=generate_messages,
            daemon=True,
            name="MessageGenerator"
        )
        generator_thread.start()
        self.logger.info("Générateur de messages de test démarré")
        
    def start_message_generator_scenario_1(self):
        """Démarre un thread qui génère le scénario 1 : Bus à pleine capacité"""
        import threading
        import time
        import random
        
        def generate_scenario_1():
            """Génère un scénario de bus à pleine capacité"""
            self.logger.info("Démarrage du générateur de messages - Scénario 1: Bus à pleine capacité")
            
            active_buses = [0, 1, 2]  # IDs des bus en service sous ensemble pour le scénario
            busy_stops = [0, 5, 10]   # IDs des arrêts à forte affluence
            available_routes = []
            if self.seed.routes and len(self.seed.routes) > 0:
                available_routes = list(self.seed.routes.keys())[:3]
            
            passenger_locations = {}  # {passenger_id: {'status': 'waiting/in_bus/arrived', 'location': stop_id/bus_id}}
            
            # Créer 10 passagers fictifs
            for p_id in range(10):
                origin = random.choice(busy_stops)
                passenger_locations[p_id] = {
                    'status': 'waiting',
                    'location': origin,
                    'destination': random.choice([s for s in busy_stops if s != origin])
                }
            
            iteration = 0
            
            while not self.stop_event.is_set():
                try:
                    iteration += 1
                    self.logger.info(f"=== Scénario 1: Itération {iteration} ===")
                    
                    if active_buses and busy_stops:
                        busy_bus = random.choice(active_buses)
                        busy_stop = random.choice(busy_stops)
                        
                        # Simuler un bus qui arrive à un arrêt chargé
                        self.message_broker.publish(Message(
                            MessageType.BUS_ARRIVAL,
                            "STSMessageGenerator",
                            {
                                'bus_id': busy_bus,
                                'stop_id': busy_stop,
                                'passenger_count': 25,
                                'available_seats': 5,
                                'route_id': random.choice(available_routes) if available_routes else "R1-A"
                            }
                        ))
                        self.logger.info(f"Bus {busy_bus} arrive à l'arrêt {busy_stop} presque plein")
                        
                        # Mise à jour de capacité pour indiquer que le bus est presque plein
                        self.message_broker.publish(Message(
                            MessageType.CAPACITY_UPDATE,
                            "STSMessageGenerator",
                            {
                                'bus_id': busy_bus,
                                'total_capacity': 30,
                                'available_seats': 5,
                                'passenger_count': 25
                            }
                        ))
                        
                        # Simuler beaucoup de passagers en attente à cet arrêt
                        self.message_broker.publish(Message(
                            MessageType.STOP_STATUS,
                            "STSMessageGenerator",
                            {
                                'stop_id': busy_stop,
                                'is_occupied': True,
                                'waiting_passengers': 15,  # on se rappelle que la limite est 10
                                'current_buses': [busy_bus]
                            }
                        ))
                        
                        time.sleep(3)  # Attendre avant la suite du scénario
                        
                        # Simuler des embarquements limités (seulement 5 personnes peuvent monter)
                        waiting_passengers = [p_id for p_id, data in passenger_locations.items() 
                                            if data['status'] == 'waiting' and data['location'] == busy_stop]
                        
                        for i, p_id in enumerate(waiting_passengers[:5]):
                            self.message_broker.publish(Message(
                                MessageType.PASSENGER_BOARDING,
                                "STSMessageGenerator",
                                {
                                    'passenger_id': p_id,
                                    'bus_id': busy_bus,
                                    'stop_id': busy_stop,
                                    'status': 'confirmed'
                                }
                            ))
                            passenger_locations[p_id]['status'] = 'in_bus'
                            passenger_locations[p_id]['location'] = busy_bus
                        
                        # Le bus est maintenant plein
                        self.message_broker.publish(Message(
                            MessageType.CAPACITY_UPDATE,
                            "STSMessageGenerator",
                            {
                                'bus_id': busy_bus,
                                'total_capacity': 30,
                                'available_seats': 0,
                                'passenger_count': 30
                            }
                        ))
                        
                        # Départ du bus à pleine capacité
                        self.message_broker.publish(Message(
                            MessageType.BUS_DEPARTURE,
                            "STSMessageGenerator",
                            {
                                'bus_id': busy_bus,
                                'stop_id': busy_stop,
                                'passenger_count': 30,
                                'next_stop_id': (busy_stop + 1) % len(busy_stops),
                                'route_id': random.choice(available_routes) if available_routes else "R1-A"
                            }
                        ))
                        self.logger.info(f"Bus {busy_bus} quitte l'arrêt {busy_stop} à pleine capacité")
                    
                    # Attendre entre les itérations
                    time.sleep(10)
                    
                except Exception as e:
                    self.logger.error(f"Erreur dans le scénario 1: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    time.sleep(10)  # Plus long délai en cas d'erreur
        
        # Créer et démarrer le thread de génération
        generator_thread = threading.Thread(
            target=generate_scenario_1,
            daemon=True,
            name="MessageGenerator-Scenario1"
        )
        generator_thread.start()
        self.logger.info("Générateur de messages - Scénario 1 démarré")


    def start_message_generator_scenario_2(self):
        """Démarre un thread qui génère le scénario 2 : Changement de route et planification"""
        import threading
        import time
        import random
        
        def generate_scenario_2():
            """Génère un scénario de changement de route et planification"""
            self.logger.info("Démarrage du générateur de messages - Scénario 2: Changement de route et planification")
            
            active_buses = [0, 1, 2]
            busy_stops = [0, 5, 10, 15, 20]   # IDs des arrêts pour la planification
            available_routes = []
            if self.seed.routes and len(self.seed.routes) > 0:
                available_routes = list(self.seed.routes.keys())[:5]  # Prendre les 5 premières routes
            
            iteration = 0
            
            while not self.stop_event.is_set():
                try:
                    iteration += 1
                    self.logger.info(f"=== Scénario 2: Itération {iteration} ===")
                    
                    if active_buses and available_routes and len(available_routes) > 1:
                        route_change_bus = random.choice(active_buses)
                        old_route = random.choice(available_routes)
                        new_route = random.choice([r for r in available_routes if r != old_route])
                        
                        # Simuler un changement de route pour un bus
                        self.message_broker.publish(Message(
                            MessageType.ROUTE_UPDATE,
                            "STSMessageGenerator",
                            {
                                'bus_id': route_change_bus,
                                'route_id': new_route,
                                'reason': 'traffic_optimization'
                            }
                        ))
                        self.logger.info(f"Bus {route_change_bus} change de route {old_route} à {new_route} pour optimisation du trafic")
                        
                        # Attendre un peu pour simuler le traitement du changement de route
                        time.sleep(2)
                        
                        # Mettre à jour horaire
                        current_time = time.time()
                        schedule_updates = {}
                        for stop_id in busy_stops:
                            # Créer un horaire progressif (on suppose que chaque arrêt à la STS est à +10 minutes)
                            arrival_time = current_time + (stop_id * 600)
                            departure_time = arrival_time + 120  # 2 minutes à chaque arrêt
                            schedule_updates[f"S{stop_id}"] = {
                                'arrival': arrival_time,
                                'departure': departure_time
                            }
                        
                        self.message_broker.publish(Message(
                            MessageType.SCHEDULE_UPDATE,
                            "STSMessageGenerator",
                            {
                                'bus_id': route_change_bus,
                                'schedule_updates': schedule_updates,
                                'frequency': 20
                            }
                        ))
                        self.logger.info(f"Nouvel horaire généré pour le bus {route_change_bus} avec {len(schedule_updates)} arrêts")
                        
                        # Simuler une notification aux arrêts concernés
                        for stop_id in busy_stops:
                            self.message_broker.publish(Message(
                                MessageType.STOP_STATUS,
                                "STSMessageGenerator",
                                {
                                    'stop_id': stop_id,
                                    'schedule_updated': True,
                                    'updated_bus_id': route_change_bus,
                                    'arrival_time': schedule_updates[f"S{stop_id}"]['arrival']
                                }
                            ))
                        
                        self.logger.info(f"Notifications envoyées à {len(busy_stops)} arrêts concernés par le nouvel horaire")
                    
                    # Attendre entre les itérations
                    time.sleep(15)
                    
                except Exception as e:
                    self.logger.error(f"Erreur dans le scénario 2: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    time.sleep(10)  # Plus long délai en cas d'erreur
        
        # Créer et démarrer le thread de génération
        generator_thread = threading.Thread(
            target=generate_scenario_2,
            daemon=True,
            name="MessageGenerator-Scenario2"
        )
        generator_thread.start()
        self.logger.info("Générateur de messages - Scénario 2 démarré")


    def start_message_generator_scenario_3(self):
        """Démarre un thread qui génère le scénario 3 : Correspondances entre bus"""
        import threading
        import time
        import random
        
        def generate_scenario_3():
            """Génère un scénario de correspondances entre bus"""
            self.logger.info("Démarrage du générateur de messages - Scénario 3: Correspondances entre bus")
            
            active_buses = list(range(5))  # IDs des bus en service (0-4)
            transfer_stops = [25, 30, 35]   # IDs des arrêts de correspondance
            passenger_locations = {}  # {passenger_id: {'status': 'waiting/in_bus/arrived', 'location': stop_id/bus_id}}
            
            # Initialiser 20 passagers pour les correspondances
            for p_id in range(20):
                passenger_locations[p_id] = {
                    'status': 'in_bus',
                    'location': p_id % len(active_buses),  # Répartir dans les différents bus
                    'destination': random.choice(transfer_stops)
                }
            
            iteration = 0
            
            while not self.stop_event.is_set():
                try:
                    iteration += 1
                    self.logger.info(f"=== Scénario 3: Itération {iteration} ===")
                    
                    if len(active_buses) >= 2 and transfer_stops:
                        transfer_stop = random.choice(transfer_stops)
                        bus1 = active_buses[0]
                        bus2 = active_buses[1]
                        
                        # Identifiez les passagers qui vont descendre pour correspondance
                        transfer_passengers = []
                        for p_id, data in passenger_locations.items():
                            if data['status'] == 'in_bus' and data['location'] == bus1 and len(transfer_passengers) < 3:
                                transfer_passengers.append(p_id)
                        
                        if transfer_passengers:  # S'il y a des passagers à transférer
                            # Bus 1 arrive avec des passagers qui vont faire une correspondance
                            self.message_broker.publish(Message(
                                MessageType.BUS_ARRIVAL,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus1,
                                    'stop_id': transfer_stop,
                                    'passenger_count': 20,
                                    'available_seats': 10
                                }
                            ))
                            self.logger.info(f"Bus {bus1} arrive à l'arrêt de correspondance {transfer_stop}")
                            
                            # Mise à jour du statut de l'arrêt pour indiquer qu'il y a un bus
                            self.message_broker.publish(Message(
                                MessageType.STOP_STATUS,
                                "STSMessageGenerator",
                                {
                                    'stop_id': transfer_stop,
                                    'is_occupied': True,
                                    'waiting_passengers': 5,
                                    'current_buses': [bus1]
                                }
                            ))
                            
                            # Simuler les passagers qui descendent pour correspondance
                            for p_id in transfer_passengers:
                                self.message_broker.publish(Message(
                                    MessageType.PASSENGER_ALIGHTING,
                                    "STSMessageGenerator",
                                    {
                                        'passenger_id': p_id,
                                        'bus_id': bus1,
                                        'stop_id': transfer_stop,
                                        'status': 'confirmed',
                                        'for_transfer': True
                                    }
                                ))
                                # Mettre à jour l'état du passager
                                passenger_locations[p_id]['status'] = 'waiting'
                                passenger_locations[p_id]['location'] = transfer_stop
                            
                            self.logger.info(f"{len(transfer_passengers)} passagers descendent pour correspondance")
                            
                            # Bus 1 part
                            self.message_broker.publish(Message(
                                MessageType.BUS_DEPARTURE,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus1,
                                    'stop_id': transfer_stop,
                                    'passenger_count': 20 - len(transfer_passengers),
                                    'next_stop_id': random.choice([s for s in transfer_stops if s != transfer_stop])
                                }
                            ))
                            
                            time.sleep(5)  # Attente entre les bus (temps de correspondance)
                            
                            # Bus 2 arrive pour la correspondance
                            self.message_broker.publish(Message(
                                MessageType.BUS_ARRIVAL,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus2,
                                    'stop_id': transfer_stop,
                                    'passenger_count': 15,
                                    'available_seats': 15
                                }
                            ))
                            self.logger.info(f"Bus {bus2} arrive pour la correspondance à l'arrêt {transfer_stop}")
                            
                            # Mise à jour du statut de l'arrêt pour indiquer la présence du bus 2
                            self.message_broker.publish(Message(
                                MessageType.STOP_STATUS,
                                "STSMessageGenerator",
                                {
                                    'stop_id': transfer_stop,
                                    'is_occupied': True,
                                    'waiting_passengers': 5 + len(transfer_passengers),
                                    'current_buses': [bus2]
                                }
                            ))
                            
                            # Mise à jour du statut du bus 2
                            self.message_broker.publish(Message(
                                MessageType.CAPACITY_UPDATE,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus2,
                                    'total_capacity': 30,
                                    'available_seats': 15,
                                    'passenger_count': 15
                                }
                            ))
                            
                            # Les passagers montent dans le bus 2
                            for p_id in transfer_passengers:
                                self.message_broker.publish(Message(
                                    MessageType.PASSENGER_BOARDING,
                                    "STSMessageGenerator",
                                    {
                                        'passenger_id': p_id,
                                        'bus_id': bus2,
                                        'stop_id': transfer_stop,
                                        'status': 'confirmed'
                                    }
                                ))
                                # Mettre à jour l'état du passager
                                passenger_locations[p_id]['status'] = 'in_bus'
                                passenger_locations[p_id]['location'] = bus2
                            
                            # Mise à jour de la capacité après embarquement
                            self.message_broker.publish(Message(
                                MessageType.CAPACITY_UPDATE,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus2,
                                    'total_capacity': 30,
                                    'available_seats': 15 - len(transfer_passengers),
                                    'passenger_count': 15 + len(transfer_passengers)
                                }
                            ))
                            
                            # Bus 2 repart avec les passagers de la correspondance
                            self.message_broker.publish(Message(
                                MessageType.BUS_DEPARTURE,
                                "STSMessageGenerator",
                                {
                                    'bus_id': bus2,
                                    'stop_id': transfer_stop,
                                    'passenger_count': 15 + len(transfer_passengers),
                                    'next_stop_id': random.choice([s for s in transfer_stops if s != transfer_stop])
                                }
                            ))
                            self.logger.info(f"Bus {bus2} repart avec {len(transfer_passengers)} passagers en correspondance")
                    
                    # Attendre entre les itérations
                    time.sleep(20)
                    
                except Exception as e:
                    self.logger.error(f"Erreur dans le scénario 3: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    time.sleep(10)  # Plus long délai en cas d'erreur
        
        # Créer et démarrer le thread de génération
        generator_thread = threading.Thread(
            target=generate_scenario_3,
            daemon=True,
            name="MessageGenerator-Scenario3"
        )
        generator_thread.start()
        self.logger.info("Générateur de messages - Scénario 3 démarré")
        
    def start_message_generator_scenario_4(self):
        """Démarre un thread qui génère le scénario 4 : Écrire un scénario de votre choix, en vous basant sur les autres"""
        # TODO  Proposer une implémentation de votre choix
        pass
    
    def start_message_generator_scenario_5(self):
        """Démarre un thread qui génère le scénario 5 : Écrire un autre scénario de votre choix, en vous basant sur les autres"""
        # TODO  Proposer une implémentation de votre choix
        pass





if __name__ == "__main__":
    # Configuration du logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exécution de la simulation
    MessageSimulationManager.run(duration=60)