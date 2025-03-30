"""
Module: message_components.py
---------------------------
Adaptation des composants du réseau STS pour utiliser le système de messagerie.

Fournit des wrappers et adaptateurs permettant aux composants existants
d'utiliser le broker de messages pour la communication.

Classes:
    MessageBusAdapter: Adaptateur pour les objets Bus
    MessageStopAdapter: Adaptateur pour les objets Stop

"""

from src.models.bus import Bus
from src.models.stop import Stop
from src.models.passenger import Passenger
from src.projects.project_2.core.message_broker import MessageBroker, Subscriber, Message, MessageType
from typing import List, Dict, Any
import logging


debug_logger = logging.getLogger("message_debug")
debug_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
debug_logger.addHandler(handler)


class MessageBusAdapter(Subscriber):
    """Adaptateur pour connecter les bus au système de messagerie"""
    
    def __init__(self, bus: Bus):
        """
        Initialise l'adaptateur pour un bus
        
        Args:
            bus: L'objet Bus à adapter
        """
        self.bus = bus
        self.broker = MessageBroker()
        self.id = f"Bus-{bus.id}"
        
        # Initialisation du logger
        self.logger = logging.getLogger(f"bus_adapter_{bus.id}")
        
        # Abonnement aux types de messages pertinents pour un bus
        self.broker.subscribe(
            self, 
            [
                MessageType.PASSENGER_BOARDING,
                MessageType.PASSENGER_ALIGHTING,
                MessageType.ROUTE_UPDATE,
                MessageType.SCHEDULE_UPDATE,
                MessageType.STOP_STATUS,
                MessageType.SYSTEM_ALERT
            ]
        )
    
    def on_message(self, message: Message) -> None:
        """
        Traite les messages reçus du broker
        
        Args:
            message: Le message reçu
        """
        import logging
        logging.getLogger("message_debug").info(f"TRACE Communication : {self.__class__.__name__} - Message de {message.sender_id} de type {message.type.value}")
        try:
            # Ignorer les messages envoyés par soi-même pour éviter les boucles
            if message.sender_id == self.id:
                return
            
            # Vérification de sécurité des données
            if not message.data or not isinstance(message.data, dict):
                return
                
            if message.type == MessageType.PASSENGER_BOARDING:
                # Un passager demande à monter
                self._handle_passenger_boarding_request(message)
                    
            elif message.type == MessageType.PASSENGER_ALIGHTING:
                # Un passager demande à descendre
                self._handle_passenger_alighting_request(message)
                        
            elif message.type == MessageType.ROUTE_UPDATE:
                # Mise à jour de route
                self._handle_route_update(message)
                
            elif message.type == MessageType.SCHEDULE_UPDATE:
                # Mise à jour d'horaire
                self._handle_schedule_update(message)
                
            elif message.type == MessageType.STOP_STATUS:
                # Mise à jour du statut d'un arrêt
                self._handle_stop_status_update(message)
                        
        except Exception as e:
            # Log de l'erreur pour debuggage
            import logging
            logging.getLogger("bus_adapter").error(f"Erreur dans on_message: {e}")
    
    def _handle_passenger_boarding_request(self, message: Message) -> None:
        """Traite une demande d'embarquement de passager"""
        passenger_id = message.data.get('passenger_id')
        stop_id = message.data.get('stop_id')
        
        if not passenger_id or not stop_id:
            return
            
        # Vérifier si le bus peut accepter ce passager
        if (self.bus.current_stop and 
            hasattr(self.bus.current_stop, 'stop_id') and
            self.bus.current_stop.stop_id == stop_id and 
            self.bus.can_accept_passengers()):
            
            # Trouver le passager à l'arrêt
            if hasattr(self.bus.current_stop, 'waiting_passengers'):
                for passenger in self.bus.current_stop.waiting_passengers:
                    if hasattr(passenger, 'id') and passenger.id == passenger_id:
                        # Accepter le passager
                        if self.bus.add_passenger(passenger):
                            # Confirmer l'embarquement
                            self.publish_passenger_boarded(passenger, stop_id)
                        break
    
    def _handle_passenger_alighting_request(self, message: Message) -> None:
        """Traite une demande de débarquement de passager"""
        passenger_id = message.data.get('passenger_id')
        stop_id = message.data.get('stop_id')
        
        if not passenger_id or not stop_id:
            return
            
        # Vérifier les conditions pour le débarquement
        if (self.bus.current_stop and 
            hasattr(self.bus.current_stop, 'stop_id') and
            self.bus.current_stop.stop_id == stop_id):
            
            # Chercher le passager dans le bus
            for passenger in self.bus.passenger_list:
                if hasattr(passenger, 'id') and passenger.id == passenger_id:
                    # Faire descendre le passager
                    if self.bus.remove_passenger(passenger):
                        # Confirmer le débarquement
                        self.publish_passenger_alighted(passenger, stop_id)
                    break
    
    def _handle_route_update(self, message: Message) -> None:
        """
        Traite une mise à jour de route pour un bus.
        
        Cette fonction gère les changements de route pour un bus, incluant
        la recherche et l'application de la nouvelle route.
        """
        # Vérifier que la mise à jour concerne bien ce bus
        if message.data.get('bus_id') != self.bus.id:
            return
        
        route_id = message.data.get('route_id')
        if not route_id:
            self.logger.warning(f"Bus {self.bus.id}: Mise à jour de route reçue sans ID de route")
            return
        
        try:
            from src.seed.stsseed import STSSeed
            seed = STSSeed()
            
            if not hasattr(seed, 'routes') or route_id not in seed.routes:
                self.logger.error(f"Bus {self.bus.id}: Route {route_id} non trouvée dans le système")
                return
            
            new_route = seed.routes[route_id]
            old_route_id = self.bus.current_route.id if self.bus.current_route else "aucune"
            self.bus.current_route = new_route
            
            # Si la route est totalement différente, aller au premier arrêt de la nouvelle route
            if (not self.bus.current_stop or 
                self.bus.current_stop not in new_route.stop_list):
                if new_route.stop_list:
                    self.bus.current_stop = new_route.stop_list[0]
                    self.logger.info(f"Bus {self.bus.id}: Repositionné au premier arrêt de la nouvelle route: {self.bus.current_stop.name}")
            
            # Publier un message informant du changement de route
            self.broker.publish(Message(
                MessageType.ROUTE_UPDATE,
                self.id,
                {
                    'component_type': 'bus',
                    'bus_id': self.bus.id,
                    'status': 'route_changed',
                    'details': {
                        'old_route': old_route_id,
                        'new_route': route_id,
                        'current_stop': self.bus.current_stop.name if self.bus.current_stop else "unknown"
                    }
                }
            ))
            
            self.logger.info(f"Bus {self.bus.id}: Route changée de {old_route_id} à {route_id}")
            
        except Exception as e:
            self.logger.error(f"Bus {self.bus.id}: Erreur lors de la mise à jour de route: {str(e)}")
    
    def _handle_schedule_update(self, message: Message) -> None:
        """
        Traite une mise à jour d'horaire.
        
        Cette fonction applique les modifications d'horaire au bus,
        en ajustant les heures de départ et d'arrivée planifiées.
        """
        # Vérifier si la mise à jour concerne toute la flotte ou juste ce bus
        target_bus_id = message.data.get('bus_id')
        if target_bus_id is not None and target_bus_id != self.bus.id:
            return
        
        schedule_updates = message.data.get('schedule_updates', {})
        if not schedule_updates:
            self.logger.warning(f"Bus {self.bus.id}: Mise à jour d'horaire reçue sans données")
            return
        
        try:
            # Créer l'attribut 'schedule' car il n'existe pas dans le modèle de base.
            if not hasattr(self.bus, 'schedule'):
                self.bus.schedule = {}
            
            # Appliquer les mises à jour d'horaire
            for stop_id, time_info in schedule_updates.items():
                if not isinstance(time_info, dict):
                    continue
                    
                arrival_time = time_info.get('arrival')
                departure_time = time_info.get('departure')
                
                # Mettre à jour l'horaire
                if stop_id not in self.bus.schedule:
                    self.bus.schedule[stop_id] = {}
                    
                if arrival_time is not None:
                    self.bus.schedule[stop_id]['arrival'] = arrival_time
                    
                if departure_time is not None:
                    self.bus.schedule[stop_id]['departure'] = departure_time
            
            # Si la mise à jour contient une modification de la fréquence
            frequency = message.data.get('frequency')
            if frequency is not None:
                if not hasattr(self.bus, 'frequency'):
                    self.bus.frequency = frequency
                else:
                    self.bus.frequency = frequency
            
            # Journaliser la mise à jour
            update_count = len(schedule_updates)
            self.logger.info(f"Bus {self.bus.id}: Horaire mis à jour pour {update_count} arrêts")
            
            # Publier une confirmation de la mise à jour
            self.broker.publish(Message(
                MessageType.SCHEDULE_UPDATE,
                self.id,
                {
                    'component_type': 'bus',
                    'bus_id': self.bus.id,
                    'status': 'schedule_updated',
                    'details': {
                        'updated_stops': list(schedule_updates.keys()),
                        'frequency_updated': frequency is not None
                    }
                }
            ))
            
        except Exception as e:
            self.logger.error(f"Bus {self.bus.id}: Erreur lors de la mise à jour d'horaire: {str(e)}")
    
    def _handle_stop_status_update(self, message: Message) -> None:
        """
        Traite une mise à jour du statut d'un arrêt.
        
        Cette fonction met à jour les informations locales du bus
        concernant l'état des arrêts, ce qui permet d'adapter son comportement.
        """
        stop_id = message.data.get('stop_id')
        if stop_id is None:
            return
        
        # Vérifier si cet arrêt est pertinent pour ce bus
        is_current_stop = (hasattr(self.bus, 'current_stop') and 
                        hasattr(self.bus.current_stop, 'stop_id') and 
                        self.bus.current_stop.stop_id == stop_id)
        
        is_next_stop = (hasattr(self.bus, 'next_stop') and 
                    hasattr(self.bus.next_stop, 'stop_id') and 
                    self.bus.next_stop.stop_id == stop_id)
        
        is_on_route = False
        if hasattr(self.bus, 'current_route') and self.bus.current_route:
            for stop in self.bus.current_route.stop_list:
                if hasattr(stop, 'stop_id') and stop.stop_id == stop_id:
                    is_on_route = True
                    break
        
        # Si l'arrêt n'est pas pertinent pour ce bus, ignorer
        if not (is_current_stop or is_next_stop or is_on_route):
            return
        
        try:
            is_occupied = message.data.get('is_occupied', False)
            waiting_passengers = message.data.get('waiting_passengers', 0)
            current_buses = message.data.get('current_buses', [])
            queued_buses = message.data.get('queued_buses', [])
            
            if not hasattr(self.bus, 'stop_statuses'):
                self.bus.stop_statuses = {}
                
            # Mettre à jour le statut de cet arrêt
            self.bus.stop_statuses[stop_id] = {
                'is_occupied': is_occupied,
                'waiting_passengers': waiting_passengers,
                'current_buses': current_buses,
                'queued_buses': queued_buses,
                'last_updated': message.timestamp
            }
            
            # Adapter le comportement du bus en fonction du statut de l'arrêt
            if is_current_stop:
                if is_occupied and self.bus.id not in current_buses:
                    self.logger.info(f"Bus {self.bus.id}: Attente à l'arrêt {stop_id} (occupé par {current_buses})")
                elif waiting_passengers > 0:
                    self.logger.info(f"Bus {self.bus.id}: {waiting_passengers} passagers en attente à l'arrêt actuel")
            
            elif is_next_stop:
                if is_occupied:
                    self.logger.info(f"Bus {self.bus.id}: Prochain arrêt {stop_id} occupé, ajustement de la vitesse")
                
                if waiting_passengers > 0:
                    self.logger.info(f"Bus {self.bus.id}: {waiting_passengers} passagers attendent au prochain arrêt")
            
            # Log général pour les arrêts sur la route
            if is_on_route and not (is_current_stop or is_next_stop):
                self.logger.debug(f"Bus {self.bus.id}: Mise à jour du statut de l'arrêt {stop_id} sur la route")
            
        except Exception as e:
            self.logger.error(f"Bus {self.bus.id}: Erreur lors du traitement du statut d'arrêt: {str(e)}")
    
    def publish_arrival(self, stop_id: int) -> None:
        """
        Publie un message d'arrivée du bus à un arrêt
        
        Args:
            stop_id: ID de l'arrêt où le bus arrive
        """
        message = Message(
            MessageType.BUS_ARRIVAL,
            self.id,
            {
                'bus_id': self.bus.id,
                'stop_id': stop_id,
                'passenger_count': len(self.bus.passenger_list),
                'available_seats': self.bus.capacity - len(self.bus.passenger_list),
                'route_id': self.bus.current_route.id if self.bus.current_route else None
            }
        )
        self.broker.publish(message)
    
    def publish_departure(self, stop_id: int) -> None:
        """
        Publie un message de départ du bus d'un arrêt
        
        Args:
            stop_id: ID de l'arrêt que le bus quitte
        """
        message = Message(
            MessageType.BUS_DEPARTURE,
            self.id,
            {
                'bus_id': self.bus.id,
                'stop_id': stop_id,
                'passenger_count': len(self.bus.passenger_list),
                'next_stop_id': self.bus.next_stop.stop_id if self.bus.next_stop else None,
                'route_id': self.bus.current_route.id if self.bus.current_route else None
            }
        )
        self.broker.publish(message)
    
    def publish_passenger_boarded(self, passenger: Passenger, stop_id: int) -> None:
        """
        Publie un message confirmant l'embarquement d'un passager
        
        Args:
            passenger: Le passager qui est monté
            stop_id: ID de l'arrêt où l'embarquement a eu lieu
        """
        message = Message(
            MessageType.PASSENGER_BOARDING,
            self.id,
            {
                'bus_id': self.bus.id,
                'passenger_id': passenger.id,
                'stop_id': stop_id,
                'status': 'confirmed',
                'available_seats': self.bus.capacity - len(self.bus.passenger_list)
            }
        )
        self.broker.publish(message)
    
    def publish_passenger_alighted(self, passenger: Passenger, stop_id: int) -> None:
        """
        Publie un message confirmant le débarquement d'un passager
        
        Args:
            passenger: Le passager qui est descendu
            stop_id: ID de l'arrêt où le débarquement a eu lieu
        """
        message = Message(
            MessageType.PASSENGER_ALIGHTING,
            self.id,
            {
                'bus_id': self.bus.id,
                'passenger_id': passenger.id,
                'stop_id': stop_id,
                'status': 'confirmed',
                'available_seats': self.bus.capacity - len(self.bus.passenger_list)
            }
        )
        self.broker.publish(message)
    
    def publish_capacity_update(self) -> None:
        """Publie une mise à jour de la capacité du bus"""
        message = Message(
            MessageType.CAPACITY_UPDATE,
            self.id,
            {
                'bus_id': self.bus.id,
                'total_capacity': self.bus.capacity,
                'available_seats': self.bus.capacity - len(self.bus.passenger_list),
                'passenger_count': len(self.bus.passenger_list)
            }
        )
        self.broker.publish(message)


class MessageStopAdapter(Subscriber):
    """Adaptateur pour connecter les arrêts au système de messagerie"""
    
    def __init__(self, stop: Stop):
        """
        Initialise l'adaptateur pour un arrêt
        
        Args:
            stop: L'objet Stop à adapter
        """
        self.stop = stop
        self.broker = MessageBroker()
        self.id = f"Stop-{stop.stop_id}"
        
        # Initialisation du logger
        self.logger = logging.getLogger(f"stop_adapter_{stop.stop_id}")
        
        # Abonnement aux types de messages pertinents pour un arrêt
        self.broker.subscribe(
            self, 
            [
                MessageType.BUS_ARRIVAL,
                MessageType.BUS_DEPARTURE,
                MessageType.PASSENGER_BOARDING,
                MessageType.PASSENGER_ALIGHTING,
                MessageType.CAPACITY_UPDATE,
                MessageType.SYSTEM_ALERT
            ]
        )
        
    
    def on_message(self, message: Message) -> None:
        """
        Traite les messages reçus du broker
        
        Args:
            message: Le message reçu
        """
        import logging
        logging.getLogger("message_debug").info(f"TRACE ON_MESSAGE: {self.__class__.__name__} - Message de {message.sender_id} de type {message.type.value}")
        try:
            
            # Ignorer les messages envoyés par soi-même pour éviter les boucles
            if message.sender_id == self.id:
                return
                
            # Vérification de sécurité des données
            if not message.data or not isinstance(message.data, dict):
                return
                
            if message.type == MessageType.BUS_ARRIVAL:
                # Un bus arrive à cet arrêt
                self._handle_bus_arrival(message)
                    
            elif message.type == MessageType.BUS_DEPARTURE:
                # Un bus quitte cet arrêt
                self._handle_bus_departure(message)
                    
            elif message.type == MessageType.PASSENGER_BOARDING:
                # Confirmation d'embarquement d'un passager
                self._handle_passenger_boarding_confirmation(message)
                    
            elif message.type == MessageType.PASSENGER_ALIGHTING:
                # Un passager est descendu à cet arrêt
                self._handle_passenger_alighting_confirmation(message)
                    
            elif message.type == MessageType.CAPACITY_UPDATE:
                # Mise à jour de la capacité d'un bus
                self._handle_capacity_update(message)
                
        except Exception as e:
            # Log de l'erreur pour debuggage
            import logging
            logging.getLogger("stop_adapter").error(f"Erreur dans on_message: {e}")
    
    def _handle_bus_arrival(self, message: Message) -> None:
        """Traite l'arrivée d'un bus à cet arrêt"""
        stop_id = message.data.get('stop_id')
        
        # Vérifier que le message concerne bien cet arrêt
        if not hasattr(self.stop, 'stop_id') or stop_id != self.stop.stop_id:
            return
            
        bus_id = message.data.get('bus_id')
        if bus_id is not None:
            # Notifier les passagers en attente
            self.publish_stop_status(bus_arrivals=[bus_id])
    
    def _handle_bus_departure(self, message: Message) -> None:
        """Traite le départ d'un bus de cet arrêt"""
        stop_id = message.data.get('stop_id')
        
        # Vérifier que le message concerne bien cet arrêt
        if not hasattr(self.stop, 'stop_id') or stop_id != self.stop.stop_id:
            return
            
        bus_id = message.data.get('bus_id')
        if bus_id is not None:
            # Mettre à jour l'état de l'arrêt
            self.publish_stop_status(bus_departures=[bus_id])
    
    def _handle_passenger_boarding_confirmation(self, message: Message) -> None:
        """Traite la confirmation d'embarquement d'un passager"""
        stop_id = message.data.get('stop_id')
        
        # Vérifier que le message concerne bien cet arrêt et qu'il s'agit d'une confirmation
        if (not hasattr(self.stop, 'stop_id') or 
            stop_id != self.stop.stop_id or 
            message.data.get('status') != 'confirmed'):
            return
            
        passenger_id = message.data.get('passenger_id')
        if passenger_id is not None and hasattr(self.stop, 'waiting_passengers'):
            # Retirer le passager de la liste d'attente
            for passenger in list(self.stop.waiting_passengers):  # Copie pour éviter les problèmes de modification
                if hasattr(passenger, 'id') and passenger.id == passenger_id:
                    self.stop.remove_passenger(passenger)
                    break
    
    def _handle_passenger_alighting_confirmation(self, message: Message) -> None:
        """
        Traite la confirmation de débarquement d'un passager.
        
        Cette fonction gère l'arrivée d'un passager à l'arrêt après qu'il
        soit descendu d'un bus, en l'ajoutant à la liste des passagers présents.
        """
        stop_id = message.data.get('stop_id')
        
        # Vérifier que le message concerne bien cet arrêt et qu'il s'agit d'une confirmation
        if (not hasattr(self.stop, 'stop_id') or 
            stop_id != self.stop.stop_id or 
            message.data.get('status') != 'confirmed'):
            return
        
        try:
            # Récupérer les informations du passager
            passenger_id = message.data.get('passenger_id')
            bus_id = message.data.get('bus_id')
            
            if not passenger_id:
                self.logger.warning(f"Arrêt {self.stop.name}: Confirmation de débarquement sans ID passager")
                return
            

            from src.seed.stsseed import STSSeed
            seed = STSSeed()
            passenger = None
            if hasattr(seed, 'passengers'):
                passenger = seed.passengers.get(passenger_id)
            
            if not passenger:
                self.logger.warning(f"Arrêt {self.stop.name}: Passager {passenger_id} non trouvé dans le système")
                return
            
            # Vérifier si le passager est déjà à cet arrêt
            is_already_here = False
            if hasattr(self.stop, 'passenger_list'):
                for p in self.stop.passenger_list:
                    if hasattr(p, 'id') and p.id == passenger_id:
                        is_already_here = True
                        break
            
            # Ajouter le passager à l'arrêt s'il n'y est pas déjà
            if not is_already_here:
                if hasattr(passenger, 'status'):
                    if hasattr(passenger, 'destination') and passenger.destination == self.stop:
                        passenger.status = "arrived"
                        self.logger.info(f"Arrêt {self.stop.name}: Passager {passenger_id} arrivé à destination")
                    else:
                        passenger.status = "waiting"
                        self.logger.info(f"Arrêt {self.stop.name}: Passager {passenger_id} en attente de correspondance")
                

                if hasattr(passenger, 'current_stop'):
                    passenger.current_stop = self.stop
                
                if hasattr(self.stop, 'add_passenger'):
                    self.stop.add_passenger(passenger)
                    self.logger.info(f"Arrêt {self.stop.name}: Passager {passenger_id} ajouté à l'arrêt après débarquement du bus {bus_id}")
                
                # Ajouter à la liste d'attente si ce n'est pas sa destination finale
                if (hasattr(self.stop, 'waiting_passengers') and
                    hasattr(passenger, 'destination') and
                    passenger.destination != self.stop):
                    if passenger not in self.stop.waiting_passengers:
                        self.stop.waiting_passengers.append(passenger)
                        self.logger.info(f"Arrêt {self.stop.name}: Passager {passenger_id} ajouté à la file d'attente")
            
            # Mettre à jour et publier le statut de l'arrêt
            self.publish_stop_status()
            
        except Exception as e:
            self.logger.error(f"Arrêt {self.stop.name}: Erreur lors du traitement du débarquement: {str(e)}")
    
    def _handle_capacity_update(self, message: Message) -> None:
        """
        Traite une mise à jour de capacité d'un bus.
        
        Cette fonction permet à l'arrêt de connaître la disponibilité des bus
        et d'optimiser l'embarquement des passagers en attente.
        """
        # Extraire les informations du bus
        bus_id = message.data.get('bus_id')
        total_capacity = message.data.get('total_capacity')
        available_seats = message.data.get('available_seats')
        passenger_count = message.data.get('passenger_count')
        
        # Vérifier que les données nécessaires sont présentes
        if None in (bus_id, available_seats):
            return
        
        try:
            # Mettre à jour le cache des capacités des bus
            if not hasattr(self.stop, 'bus_capacities'):
                self.stop.bus_capacities = {}
            
            # Stocker les informations de capacité
            self.stop.bus_capacities[bus_id] = {
                'total_capacity': total_capacity,
                'available_seats': available_seats,
                'passenger_count': passenger_count,
                'last_updated': message.timestamp
            }
            
            # Vérifier si ce bus est actuellement à cet arrêt
            bus_at_stop = False
            if hasattr(self.stop, 'current_buses'):
                for bus in self.stop.current_buses:
                    if hasattr(bus, 'id') and bus.id == bus_id:
                        bus_at_stop = True
                        break
            
            # Si le bus est à cet arrêt et qu'il reste des places disponibles
            if bus_at_stop and available_seats > 0:
                suitable_passengers = []
                
                if hasattr(self.stop, 'waiting_passengers'):
                    from src.seed.stsseed import STSSeed
                    seed = STSSeed()
                    
                    # Récupérer le bus pour vérifier sa route
                    bus_obj = seed.buses.get(bus_id) if hasattr(seed, 'buses') else None
                    
                    if bus_obj and hasattr(bus_obj, 'current_route') and bus_obj.current_route:
                        route_stops = []
                        if hasattr(bus_obj.current_route, 'stop_list'):
                            route_stops = bus_obj.current_route.stop_list
                        
                        for passenger in self.stop.waiting_passengers:
                            can_board = False
                            
                            if hasattr(passenger, 'destination'):
                                if passenger.destination in route_stops:
                                    can_board = True
                                elif hasattr(passenger.destination, 'stop_list'):
                                    for stop in passenger.destination.stop_list:
                                        if stop in route_stops:
                                            can_board = True
                                            break
                            
                            if can_board:
                                suitable_passengers.append(passenger)
                
                # Si des passagers peuvent prendre ce bus, les trier par priorité
                if suitable_passengers and len(suitable_passengers) > 0:
                    def get_priority(passenger):
                        category_priority = {
                            'Senior': 3,
                            'Regular': 2,
                            'Student': 1
                        }
                        
                        # Obtenir la priorité de la catégorie ou la valeur par défaut
                        category = getattr(passenger, 'category', 'Regular')
                        return category_priority.get(category, 2)
                    
                    # Trier les passagers par priorité décroissante
                    suitable_passengers.sort(key=get_priority, reverse=True)
                    
                    # Limiter le nombre de passagers à embarquer selon les places disponibles
                    passengers_to_board = suitable_passengers[:available_seats]
                    
                    # Demander l'embarquement pour chaque passager éligible
                    for passenger in passengers_to_board:
                        if hasattr(passenger, 'id'):
                            self.logger.info(f"Arrêt {self.stop.name}: Demande d'embarquement pour le passager {passenger.id} dans le bus {bus_id}")
                            self.request_boarding(passenger, bus_id)
            
            
        except Exception as e:
            self.logger.error(f"Arrêt {self.stop.name}: Erreur lors du traitement de la mise à jour de capacité: {str(e)}")
    
    def publish_stop_status(self, bus_arrivals=None, bus_departures=None) -> None:
        """
        Publie l'état actuel de l'arrêt
        
        Args:
            bus_arrivals: Liste des ID des bus qui viennent d'arriver
            bus_departures: Liste des ID des bus qui viennent de partir
        """
        current_buses = [bus.id for bus in self.stop.get_current_buses()]
        queued_buses = [bus.id for bus in self.stop.bus_queue]
        
        message = Message(
            MessageType.STOP_STATUS,
            self.id,
            {
                'stop_id': self.stop.stop_id,
                'stop_name': self.stop.name,
                'is_occupied': self.stop.is_occupied,
                'waiting_passengers': len(self.stop.waiting_passengers),
                'current_buses': current_buses,
                'queued_buses': queued_buses,
                'bus_arrivals': bus_arrivals or [],
                'bus_departures': bus_departures or []
            }
        )
        self.broker.publish(message)
    
    def request_boarding(self, passenger: Passenger, target_bus_id: int) -> None:
        """
        Demande l'embarquement d'un passager dans un bus spécifique
        
        Args:
            passenger: Le passager qui souhaite embarquer
            target_bus_id: L'ID du bus ciblé
        """
        
        # Vérification que l'arrêt et le passager ont les attributs nécessaires
        if not hasattr(self.stop, 'stop_id') or not hasattr(passenger, 'id'):
            import logging
            logging.getLogger("stop_adapter").error(
                f"Impossible de demander l'embarquement: attributs manquants"
            )
            return
            
        message = Message(
            MessageType.PASSENGER_BOARDING,
            self.id,
            {
                'passenger_id': passenger.id,
                'stop_id': self.stop.stop_id,
                'bus_id': target_bus_id,
                'category': getattr(passenger, 'category', 'Regular'),
                'destination_id': getattr(passenger.destination, 'id', None) if hasattr(passenger, 'destination') else None,
                'status': 'requested'
            }
        )
        self.broker.publish(message)