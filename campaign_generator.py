"""
campaign_generator_ui.py
------------------------

This module provides a simple graphical interface for generating
role‑playing game campaigns based on different settings: Fantasy,
Science‑Fiction, Modern and Post‑Apocalyptic.  The UI is built using
Tkinter with ttk widgets for a clean look.  Users select a setting,
generate a random campaign using the corresponding generator module,
view the results, and export the details to a Word (.docx) document.

The program falls back on a minimal DOCX implementation to avoid
requiring external libraries.  It creates a valid Word document by
zipping together the necessary XML parts whenever the user chooses to
export.

To run the application: ``python3 campaign_generator_ui.py``.  A window
will open allowing you to select the setting and generate a campaign.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import zipfile
from typing import Dict, List
import json


# ---------------------------------------------------------------------------
# Campaign data tables for each setting
#
# Each setting includes its own lists of starting locations, quests, hooks,
# quest givers, NPC archetypes, regions, distances, encounters, rewards,
# penalties and quest items.  When generating a campaign the appropriate
# random entry is selected from each list.  These tables are adapted from the
# generator scripts and paraphrase the content from the FlexTale Campaign
# Generator where appropriate.

import random


def roll(table: List[str]) -> str:
    """Return a random entry from a table."""
    return random.choice(table)


# Fantasy tables (seeds)
FANTASY_STARTING_LOCATIONS: List[str] = [
    "Tavern – The stereotypical place for a band of adventurers to meet for the first time.",
    "Jail – The entire party has been jailed for a (real or trump‑up) crime; swapping stories passes the time.",
    "Dinner Party – An influential NPC has invited the heroes to a fancy meal and offers them their first job.",
    "Faction Hall – The characters all belong to the same faction and meet during one of its gatherings.",
    "Mutual Friend – Every PC knows the same NPC and happens to visit them at the same moment.",
    "Job Board – A bulletin board advertises quests; the party converges on the same posting and decides to join forces.",
    "Security Corruption – Each hero has been accused of a crime and may undertake a minor task instead of facing judgment.",
    "Festival Chaos – A settlement’s festival goes awry; amid the chaos the heroes notice one another.",
    "Marketplace Disaster – At a bustling bazaar a pickpocket triggers disaster, thrusting the PCs into the centre of events.",
    "Shared Journey – The party is travelling together on a ship or caravan and bonds over the long ride.",
    "Funeral – All of the heroes attend the burial of an NPC they each knew in some way.",
    "Catastrophe Survivors – A city‑wide calamity strikes; amid the rubble and smoke the PCs find one another.",
]

FANTASY_QUEST_TEMPLATES: List[str] = [
    "Chase – An NPC snatches a purse and bolts; the party gives chase through crowded streets.",
    "Clear Out 1d6 Threats – Monsters have invaded a community; the heroes must drive off 1d6 of them.",
    "Clear Out 2d6 Threats – A larger group of foes threatens the town; the heroes must defeat 2d6 foes.",
    "Collect Trophies – The adventurers must slay creatures in the wild and harvest 3d6 valuable trophies.",
    "Assassinate – Eliminate a specific NPC who endangers the community.",
    "Escort Caravan – Protect a caravan trade group to a distant settlement; expect 1d4 monster attacks en route.",
    "Escort Pilgrim – Safely accompany an NPC on a pilgrimage to a point of interest; random encounters are likely.",
    "Courier Delivery – Carry a special item to an NPC in a distant settlement, facing both human and monster encounters on the way.",
    "Rescue Captives – Free 1d6 captured townsfolk from a monster’s lair; each life saved or lost affects the reward and penalty.",
    "Gather Herbs – Search the wilderness for 2d6 rare herbs; there’s a chance of finding each and of being ambushed.",
    "Stop Ritual – Prevent a deranged NPC from sacrificing a hostage at midnight.",
    "Scout Ahead – Explore 2d8 unexplored hexes and report back to the quest‑giver.",
]

FANTASY_QUEST_HOOKS: List[str] = [
    "Wealthy Patron – A noble or merchant pays handsomely to get something done.",
    "Sensitive Matter – Officials privately ask for help because they can’t act openly.",
    "City Under Siege – The city or faction the PCs care about is threatened if the quest fails.",
    "Known NPC in Danger – A friend or ally of the party will be harmed if the quest fails.",
    "Disrupts Major Event – The quest interferes with a festival or important occasion.",
    "Air of Mystery – A mysterious stranger or anonymous letter intrigues the curious.",
    "Prophetic Declaration – A prophecy or divination foretells the PCs’ involvement or doom.",
    "Chance Discovery – The heroes stumble upon the quest’s trigger – a lost letter or grisly clue.",
    "Righteous Revenge – Completing the quest helps someone gain revenge on a villain.",
    "Plea of the Innocent – A desperate, helpless person begs for the heroes’ aid.",
    "Official Decree – The state, church or militia mandates that the heroes carry out the mission.",
    "Faction Assignment – A faction with which a PC is affiliated needs this task completed.",
]

FANTASY_QUEST_GIVERS: List[str] = [
    "Political Leader – A mayor, magistrate or similar authority; success yields further missions, failure risks imprisonment.",
    "Security Leader – A captain of the guard or city watch; success buys leniency for future infractions.",
    "Faction Leader – A high‑ranking member of a guild, church or secret society; success may earn membership.",
    "Divine Leader – A priest, shaman or other spiritual guide; success grants blessings, failure invites divine wrath.",
    "Noble – A wealthy private citizen; success doubles monetary reward while failure creates a powerful enemy.",
    "Merchant – A tradesperson whose profession relates to the task; PCs with relevant skills gain camaraderie.",
    "Artisan – A skilled crafter; characters with similar abilities gain camaraderie.",
    "Military Leader – A captain or lieutenant who commands formal forces.",
    "Class Leader – A veteran adventurer of a particular class who offers guidance and quests.",
    "Commoner – A generic townsfolk; no special bonuses or penalties for success or failure.",
    "Elder or Scholar – A knowledgeable individual; PCs trained in related skills gain camaraderie.",
    "Hermit or Beggar – A seemingly insignificant figure who may secretly be someone else in disguise.",
]

FANTASY_NPC_QUICK_PICK: List[str] = [
    "Beggar – A destitute villager with barely a coin to their name and little ability to defend themselves.",
    "Farmer – A simple villager with a rustic weapon and a few silver pieces.",
    "Merchant – A shrewd trader armed with a dagger and short sword and a modest purse.",
    "Rogue – A slippery scoundrel skilled with blades and bow, keen to profit from any situation.",
    "Fighter – A hardened warrior wearing chainmail and carrying martial weapons.",
    "Barbarian – A ferocious combatant wielding a greataxe and throwing axes, clad in minimal armour.",
    "Druid – A nature‑priest armed with a quarterstaff and sling, clad in simple garments.",
    "Cleric – A divine spellcaster bearing a mace, shield and crossbow, with a sacred icon.",
    "Wizard – A studious mage protected by enchanted robes and armed with a crossbow and dagger.",
    "Bard – A charismatic performer who fights with rapier and bow while playing a lute.",
    "Ranger – A rugged hunter skilled with sword and bow and at home in the wilderness.",
    "Noble – A refined aristocrat with coin to spare and influence to wield.",
]

FANTASY_TERRAIN_TYPES: List[str] = [
    "Urban – busy streets, winding alleys and teeming marketplaces.",
    "Plains – rolling fields and open grasslands.",
    "Hills – rugged terrain dotted with rocky outcroppings.",
    "Forest – dense woods filled with animal life and hidden paths.",
    "Jungle – thick vegetation, exotic creatures and humid conditions.",
    "Desert – arid dunes, scorching sun and occasional oases.",
    "Swamp – marshy ground, fetid water and lurking dangers.",
    "Mountain – steep slopes, snow‑capped peaks and treacherous passes.",
    "Coastal – sandy beaches, cliffs and the ever‑present sea breeze.",
    "Aquatic – open water, reefs and the mysteries beneath the waves.",
    "Underground – caverns, tunnels and subterranean chambers.",
]

FANTASY_OVERLAND_DISTANCES: List[str] = [
    "Neighbouring Hex – just next door.",
    "1d4 Hexes – between one and four hexes away.",
    "1d8 Hexes – between one and eight hexes distant.",
    "2d8 Hexes – a moderate journey through several hexes.",
    "3d12 Hexes – a long trek across diverse terrain.",
    "4d20 Hexes – an epic expedition across a vast region.",
    "1 Week’s Ride – roughly one week of travel by horse.",
    "1d4 Weeks’ Ride – anywhere from one to four weeks in the saddle.",
    "1 Month’s Ride – approximately a month of overland travel.",
    "Neighbouring Terrain Region – an adjacent area with a different terrain type.",
    "Neighbouring Nation – across a border into a new country.",
    "Neighbouring Continent – across the sea to a distant land.",
]

FANTASY_RANDOM_ENCOUNTERS: List[str] = [
    "Bandit Ambush – A group of highwaymen attempt to rob the party.",
    "Wandering Merchant – A travelling trader offers unusual wares and rumours.",
    "Wolf Pack – Hungry wolves stalk the heroes through the night.",
    "Violent Storm – Torrential rain and lightning slow progress and test endurance.",
    "Lost Traveller – A lone wanderer begs for help reaching the next settlement.",
    "Hidden Trap – A pitfall or snare threatens to injure the unwary.",
    "Ancient Ruins – Crumbling structures hint at forgotten civilisations.",
    "Magic Anomaly – A wild surge of arcane energy causes strange effects.",
    "Guard Patrol – Local soldiers question the party’s motives and demand papers.",
    "Wild Animals – A herd of elk, a boar or other beasts crosses the party’s path.",
    "River Crossing – A swollen river blocks the way; fording it is dangerous.",
    "Orc Raiders – A band of orcs raids a nearby homestead, daring the heroes to intervene.",
]

FANTASY_REWARDS: List[str] = [
    "A purse of gold and silver coins.",
    "A minor magical item useful for the next adventure.",
    "The gratitude of a local faction, granting favours in the future.",
    "Land or a small house in the settlement.",
    "A valuable piece of art or jewellery.",
    "Secret knowledge or a map leading to another quest.",
    "A noble title or honorary rank.",
    "A rare potion or healing elixir.",
    "A blessed weapon or holy symbol.",
    "An animal companion or mount.",
    "A trove of gemstones and trade goods.",
    "Friendship and ongoing support from the quest‑giver.",
]

FANTASY_PENALTIES: List[str] = [
    "Heavy fines taken by the authorities.",
    "Confiscation of equipment or property.",
    "Loss of standing within a faction or guild.",
    "A curse or lingering injury afflicts a hero.",
    "Imprisonment or exile from the settlement.",
    "A powerful enemy sworn to seek revenge.",
    "Bounty hunters sent after the party.",
    "Betrayal by an NPC ally.",
    "Damage to a valued magical item.",
    "A companion NPC dies or is captured.",
    "Bad omen that hinders future endeavours.",
    "No immediate penalty – the party simply fails and loses time.",
]

FANTASY_QUEST_ITEMS: List[str] = [
    "Master‑crafted instrument – An exquisitely made musical instrument sought by a bard.",
    "Signet ring – A ring bearing the crest of a noble house, needed to prove identity.",
    "Special key – A unique key required to open a sealed vault or chest.",
    "Potion ingredients – Rare herbs and reagents needed for powerful elixirs.",
    "Religious token – A relic sacred to a faith, essential for a ritual.",
    "Ancient map – A parchment that marks an unexplored ruin.",
    "Runed stone – A carved stone inscribed with arcane runes.",
    "Dragon scale – A prized piece of hide used in crafting armour or magic.",
    "Cursed amulet – A mysterious necklace rumoured to bring misfortune.",
    "Phoenix feather – A rare feather that can resurrect the dead or power spells.",
    "Hero’s journal – A journal containing the secrets of a legendary adventurer.",
    "Summoning scroll – A scroll capable of calling a powerful being.",
]


def generate_fantasy_campaign() -> Dict[str, str]:
    """Generate a random fantasy campaign outline using detailed paragraphs.

    Each entry is constructed by rolling multiple times on various tables to
    produce a longer, multi‑sentence description.  Seeds from the
    FlexTale tables are occasionally used as the first component to retain
    authenticity, but additional random rolls flesh out the context,
    motives, hazards and rewards.  This approach satisfies the request
    for longer entries while still ensuring hundreds of unique
    combinations per category.
    """
    campaign: Dict[str, str] = {}
    # Compose each field using the dedicated helper functions
    campaign["Starting Location"] = compose_detailed_starting("Fantasy")
    campaign["Quest"] = compose_detailed_quest("Fantasy")
    campaign["Quest Hook"] = compose_detailed_hook("Fantasy")
    campaign["Quest Giver"] = compose_detailed_giver("Fantasy")
    campaign["Key NPC"] = compose_detailed_npc("Fantasy")
    campaign["Region"] = compose_detailed_region("Fantasy")
    campaign["Travel Distance"] = compose_detailed_distance("Fantasy")
    campaign["Random Encounter"] = compose_detailed_encounter("Fantasy")
    campaign["Reward"] = compose_detailed_reward("Fantasy")
    campaign["Penalty"] = compose_detailed_penalty("Fantasy")
    campaign["Quest Item"] = compose_detailed_item("Fantasy")
    return campaign


# Sci‑Fi tables
SCI_STARTING_LOCATIONS: List[str] = [
    "Space Tavern – A raucous bar aboard a spinning station where starfarers exchange tales.",
    "Brig – The PCs awaken in a detention cell aboard a patrol cruiser accused of a crime.",
    "Diplomatic Dinner – A high‑ranking official invites the crew to a gala on a luxury liner and offers a clandestine mission.",
    "Guild Hall – Members of the same interstellar guild meet at a chapterhouse on a core world.",
    "Mutual Contact – A shared fixer or mentor summons the crew to their asteroid hideout.",
    "Job Board – The crew answers the same holoposted contract on a public bounty board.",
    "Blackmail – Each hero receives an anonymous threat and must cooperate to clear their names.",
    "Festival Flare – A planetary celebration of first contact erupts into chaos; amidst the confusion the PCs meet.",
    "Market Meltdown – A cyber‑attack causes havoc in a bustling trade bazaar, forcing strangers to work together.",
    "Shared Passage – Travellers aboard a long‑haul freighter bond over days in hyperspace.",
    "Memorial – All are present at the memorial of a mutual crewmate lost in a battle.",
    "Disaster Survivors – The PCs are among the few survivors of a station catastrophe and must stick together.",
]

SCI_QUEST_TEMPLATES: List[str] = [
    "Pursue Pirate – Track down a pirate ship that stole experimental tech and retrieve it.",
    "Clear Out Nest – Drive out alien vermin infesting a space station’s vent network.",
    "Purge the Core – Overload a reactor core crawling with hostile nanobots before it melts down.",
    "Harvest Specimens – Collect biological samples from a xenobiological reserve world.",
    "Neutralise Target – Assassinate a rogue AI hiding in a clandestine data fortress.",
    "Escort Convoy – Protect a fleet of cargo haulers through a pirate‑infested sector.",
    "Guard Pilgrim – Escort a religious envoy to a remote shrine in a nebula.",
    "Deliver Payload – Smuggle a sealed container to a contact on an industrial moon.",
    "Rescue Hostages – Free colonists held by raiders on a deserted mining facility.",
    "Gather Resources – Mine rare minerals from an asteroid belt while avoiding hazards.",
    "Stop Ritual – Interrupt a cult attempting to summon an extradimensional entity via wormhole.",
    "Chart the Unknown – Survey uncharted sectors and scan for anomalies.",
]

SCI_QUEST_HOOKS: List[str] = [
    "Corporate Contract – A mega‑corp offers lavish credits for a discreet job.",
    "Shadow Op – Authorities secretly recruit the PCs for a mission outside normal channels.",
    "Station Under Siege – The habitat where the PCs live will fall if the mission fails.",
    "Personal Stakes – Someone close to the crew is endangered or implicated.",
    "Event Crash – The mission threatens to derail a high‑profile launch or summit.",
    "Mysterious Transmission – An encrypted message contains only coordinates and a plea.",
    "Prophetic Dream – A precognitive vision shows doom unless the crew intervenes.",
    "Accidental Discovery – The heroes stumble upon evidence of a conspiracy in a data cache.",
    "Vengeance – A contact seeks justice against a corporate or criminal foe.",
    "Desperate Plea – Refugees beg the crew to intervene before catastrophe strikes.",
    "Official Directive – A planetary governor or fleet admiral orders the job done.",
    "Faction Mission – A guild or clan to which a PC belongs needs this task completed.",
]

SCI_QUEST_GIVERS: List[str] = [
    "Admiral – A fleet commander promising resources and promotions for success.",
    "Security Chief – The head of a station’s security offering clearance in exchange for aid.",
    "Guild Master – A leader of a trade guild who can grant membership or expel transgressors.",
    "High Priest – A spiritual leader whose blessing carries weight among believers.",
    "Corporate Executive – A rich CEO who rewards handsomely but expects results.",
    "Quartermaster – A logistician who trades in favours and equipment.",
    "Engineer – A brilliant mechanic who needs help with an impossible project.",
    "Captain – A veteran starship captain who hires reliable crews.",
    "Veteran Mercenary – A seasoned soldier of fortune offering guidance.",
    "Spacer – A common crew member needing help with a personal problem.",
    "Scientist – An academic offering research grants and knowledge.",
    "Unknown Benefactor – A mysterious patron whose true identity is concealed.",
]

SCI_NPC_QUICK_PICK: List[str] = [
    "Android – A synthetic being with advanced processing power and limited emotions.",
    "Spacer – An experienced spacefarer with stories from every corner of the galaxy.",
    "Merchant – A savvy trader dealing in rare goods and shady information.",
    "Smuggler – A charismatic rogue adept at getting contraband through customs.",
    "Marine – A heavily armed soldier trained for boarding actions and zero‑G fights.",
    "Engineer – A grease‑stained genius who can fix or jury‑rig any technology.",
    "Medic – A field doctor with cybernetic tools and battlefield experience.",
    "Scientist – An intellectual specialising in xenobiology, astrophysics or another field.",
    "Pilot – A hotshot navigator and ace dogfighter.",
    "Diplomat – A smooth negotiator skilled at resolving interspecies conflicts.",
    "Hacker – A cyber specialist capable of infiltrating secure networks.",
    "Noble – A scion of a powerful house with political clout and resources.",
]

SCI_TERRAIN_TYPES: List[str] = [
    "Space Station – Habitat rings, docking bays and maintenance shafts.",
    "Planetary Surface – Diverse biomes from deserts to jungles on alien worlds.",
    "Asteroid Belt – Floating rocks, mining outposts and zero‑G hazards.",
    "Nebula – Colourful gas clouds that disrupt sensors and hide dangers.",
    "Derelict Ship – Abandoned hulks, dark corridors and unknown cargo.",
    "Orbital Shipyard – Expansive yards with half‑constructed vessels and cranes.",
    "Artificial Habitat – Luxury arcologies, biodomes and corporate enclaves.",
    "Deep Space – Empty vacuum punctuated by the occasional passing comet.",
    "Alien Ruins – Ancient structures filled with enigmatic tech and traps.",
    "Ice World – Glacial landscapes, frozen oceans and hidden caverns.",
    "Gas Giant – Swirling storms, floating platforms and pressure hazards.",
]

SCI_OVERLAND_DISTANCES: List[str] = [
    "Adjacent Hex – next door in the same sector.",
    "1–4 Hexes – up to four hexes across the star map.",
    "1–8 Hexes – a modest journey requiring a few hyperspace jumps.",
    "2–8 Hexes – a longer trip spanning multiple sub‑sectors.",
    "3–12 Hexes – a significant voyage across regions of space.",
    "4–20 Hexes – an epic trek across half the galaxy.",
    "1 Week’s Flight – roughly one week in realspace transit.",
    "1–4 Weeks’ Flight – between one and four weeks traversing space lanes.",
    "1 Month’s Flight – approximately a month cruising between stars.",
    "Neighbouring Sector – cross into an adjacent region with different dangers.",
    "Neighbouring Power – travel to territory controlled by a different polity.",
    "Neighbouring Galaxy – leap to an entirely new galaxy via ancient gate.",
]

SCI_RANDOM_ENCOUNTERS: List[str] = [
    "Space Pirates – Raiders attack in sleek fighters demanding tribute.",
    "Derelict SOS – A distress call leads to a drifting, seemingly empty ship.",
    "Meteor Shower – Micrometeoroids pelt hulls and threaten to puncture.",
    "Solar Flare – A stellar eruption disrupts electronics and shields.",
    "Stowaway – Someone hides in the cargo hold seeking passage or trouble.",
    "Gravity Well – A hidden gravity mine or stellar phenomenon pulls ships off course.",
    "Alien Probe – An unmanned device scans the crew and transmits unknown data.",
    "Rival Crew – Another adventuring team crosses paths; conflict or collaboration ensues.",
    "Holographic Trap – A simulated environment lures the PCs into a false sense of safety.",
    "Refuelling Request – A stranded civilian ship pleads for help.",
    "Nanotech Swarm – A cloud of self‑replicating machines begins to consume metal.",
    "Ancient Sentinel – A dormant guardian robot awakens and tests intruders.",
]

SCI_REWARDS: List[str] = [
    "A cache of precious metals and credit chips.",
    "Prototype tech granting an edge in future missions.",
    "Corporate shares or favour with a mega‑corp.",
    "A deed to a small freighter or outpost.",
    "An alien artefact of unknown power.",
    "Access codes to restricted systems or space lanes.",
    "An honorary title within a planetary government.",
    "Advanced medical kits or cybernetic implants.",
    "A blaster or energy shield with a unique property.",
    "A loyal robot or drone companion.",
    "A crate of rare starship parts and spare drives.",
    "An introduction to a powerful contact on a core world.",
]

SCI_PENALTIES: List[str] = [
    "Heavy fines deducted directly from the crew’s accounts.",
    "Revocation of docking privileges at major stations.",
    "Loss of standing with a guild or corporate sponsor.",
    "Implantation of a tracking or control device.",
    "Confiscation of the crew’s ship or equipment.",
    "A sworn vendetta by a powerful crime syndicate.",
    "A bounty issued across multiple systems.",
    "A trusted NPC dies or turns against the crew.",
    "Sabotage of the crew’s ship by unknown enemies.",
    "Temporary suppression of FTL capabilities.",
    "A rival crew claims the promised reward instead.",
    "No immediate penalty – simply a lost opportunity and reputation hit.",
]

SCI_QUEST_ITEMS: List[str] = [
    "Encrypted data chip containing sensitive information.",
    "Alien crystal that emits a mysterious energy signature.",
    "Prototype weapon slated for testing by a military contractor.",
    "Stasis pod holding an unknown lifeform.",
    "Ancient star map pointing to a lost sector.",
    "Quantum key required to access a sealed research facility.",
    "Relic from a long‑dead civilisation revered by multiple species.",
    "Medical serum that can cure a rare spaceborne virus.",
    "Personal AI core belonging to a renowned scientist.",
    "A shipment of illegal cybernetics destined for the black market.",
    "The genetic sequencing of a newly discovered species.",
    "A portable fusion generator needed to power a colony.",
]


def generate_scifi_campaign() -> Dict[str, str]:
    """Generate a random science‑fiction campaign with detailed paragraphs.

    Like the fantasy generator, this function uses multi‑roll
    compositions to create rich descriptions for each campaign element.
    The variety of table entries combined with additional context and
    hazards ensures a large pool of possible outputs.
    """
    campaign: Dict[str, str] = {}
    campaign["Starting Location"] = compose_detailed_starting("Sci‑Fi")
    campaign["Quest"] = compose_detailed_quest("Sci‑Fi")
    campaign["Quest Hook"] = compose_detailed_hook("Sci‑Fi")
    campaign["Quest Giver"] = compose_detailed_giver("Sci‑Fi")
    campaign["Key NPC"] = compose_detailed_npc("Sci‑Fi")
    campaign["Region"] = compose_detailed_region("Sci‑Fi")
    campaign["Travel Distance"] = compose_detailed_distance("Sci‑Fi")
    campaign["Random Encounter"] = compose_detailed_encounter("Sci‑Fi")
    campaign["Reward"] = compose_detailed_reward("Sci‑Fi")
    campaign["Penalty"] = compose_detailed_penalty("Sci‑Fi")
    campaign["Quest Item"] = compose_detailed_item("Sci‑Fi")
    return campaign


# Modern tables
MODERN_STARTING_LOCATIONS: List[str] = [
    "Coffee Shop – A trendy café where strangers overhear the same conversation and connect.",
    "Police Station Holding Cell – The PCs are arrested together for unrelated misdemeanours.",
    "Fundraiser Gala – An influential benefactor invites the characters to a charity event and pitches a job.",
    "Community Center – Members of the same club or organisation meet at a local hall.",
    "Mutual Friend’s Loft – A shared acquaintance summons everyone for help with a problem.",
    "Job Board App – The group accepts the same gig on a crowdsourced work platform.",
    "Blackmail Email – Anonymous threats force the PCs to co‑operate to clear their names.",
    "Street Festival – A city celebration descends into chaos; in the commotion, the characters band together.",
    "Market Panic – A fire or robbery at a farmers’ market throws strangers into a shared crisis.",
    "Train Ride – Commuters on a long train journey strike up conversation and discover a shared purpose.",
    "Memorial Service – All attend the funeral of a mentor, bonding over shared memories.",
    "Disaster Shelter – Survivors of a natural disaster find each other in a temporary shelter.",
]

MODERN_QUEST_TEMPLATES: List[str] = [
    "Pursue Thief – Track down a pickpocket who stole sensitive documents.",
    "Clear Out Gang – Help police remove a violent gang from a neighbourhood.",
    "Defuse Bomb – Locate and deactivate an improvised explosive before it detonates.",
    "Collect Evidence – Gather surveillance footage and statements to prove wrongdoing.",
    "Neutralise Target – Take down a dangerous criminal without causing collateral damage.",
    "Escort Convoy – Protect a VIP convoy through a protest‑ridden part of town.",
    "Protect Witness – Escort a key witness safely to court amid threats.",
    "Deliver Package – Transport a briefcase containing legal documents to a courthouse under a time limit.",
    "Rescue Hostages – Free employees held during a bank robbery.",
    "Gather Supplies – Acquire medical supplies and food for a community after a storm.",
    "Stop Ritual – Shut down an illegal underground fight ring before someone is hurt.",
    "Scout Ahead – Survey an abandoned factory for hazards before redevelopment.",
]

MODERN_QUEST_HOOKS: List[str] = [
    "Generous Employer – A wealthy investor offers substantial payment for a discreet favour.",
    "Off‑the‑Books – Authorities privately ask for help outside normal procedures.",
    "Neighbourhood Threat – The PCs’ own neighbourhood will suffer if the task fails.",
    "Personal Connection – A family member or friend is directly affected.",
    "Event Disruption – The mission coincides with a major public event, raising the stakes.",
    "Mystery Caller – An unknown voice provides only a location and plea for help.",
    "Foreboding Dream – An unnerving dream suggests disaster unless action is taken.",
    "Accidental Discovery – The heroes stumble upon incriminating files while doing something else.",
    "Revenge – Someone seeks justice against a corrupt individual or corporation.",
    "Help the Helpless – Vulnerable people beg for assistance the authorities won’t provide.",
    "Official Order – A judge or police chief orders the party to act.",
    "Organisation Mission – A labour union, activist group or secret society needs the job done.",
]

MODERN_QUEST_GIVERS: List[str] = [
    "Police Chief – A top cop who can grant leniency or crack down hard.",
    "Detective – An investigator sharing leads and needing help with a case.",
    "Journalist – A reporter promising exposure in exchange for ground‑level work.",
    "Clergy – A community pastor or imam seeking aid for parishioners.",
    "CEO – A corporate executive offering rewards and leverage.",
    "Supplier – A logistics manager who trades in favours and equipment.",
    "Mechanic – An expert fixer needing help procuring parts or dealing with tough clients.",
    "Captain – A former military officer now running private security.",
    "Veteran Operative – A retired agent offering expertise and connections.",
    "Average Citizen – A neighbour who simply needs help.",
    "Professor – An academic requiring assistance with research or protection.",
    "Anonymous Patron – A benefactor hiding their identity behind an app.",
]

MODERN_NPC_QUICK_PICK: List[str] = [
    "Detective – A seasoned investigator with a nose for trouble.",
    "Street Kid – A savvy youth with connections on every corner.",
    "Entrepreneur – A small business owner juggling risks and rewards.",
    "Thief – A quick‑fingered rogue adept at sleight of hand.",
    "Bodyguard – A trained protector skilled in hand‑to‑hand combat.",
    "Mechanic – A gearhead who can repair cars, bikes or electronics.",
    "Paramedic – A medic who keeps people alive in dangerous situations.",
    "Lawyer – A legal eagle with knowledge of loopholes and precedents.",
    "Hacker – A cyber specialist who lives online and cracks systems.",
    "Politician – A public servant juggling constituents and personal ambition.",
    "Journalist – A storyteller hunting scoops and truth.",
    "Wealthy Heir – A privileged individual with resources and influence.",
]

MODERN_TERRAIN_TYPES: List[str] = [
    "Downtown – Skyscrapers, busy streets and corporate headquarters.",
    "Suburb – Residential streets, shopping centres and schools.",
    "Industrial Park – Factories, warehouses and rail spurs.",
    "Rural Farmland – Fields, barns and quiet country roads.",
    "Wilderness Park – Forested public lands and hiking trails.",
    "Shopping Mall – Indoor plazas, boutiques and food courts.",
    "University Campus – Lecture halls, labs and dormitories.",
    "Beachfront – Boardwalks, piers and beaches with tourists.",
    "Underground Tunnel – Sewers, subways and service conduits.",
    "Airport – Terminals, runways and baggage areas.",
    "Highway – Motorways, rest stops and gas stations.",
    "Harbour – Docks, warehouses and watercraft.",
]

MODERN_OVERLAND_DISTANCES: List[str] = [
    "Neighbouring Block – just around the corner.",
    "1–4 Blocks – a short walk across town.",
    "1–8 Blocks – a modest stroll or quick drive.",
    "2–8 Blocks – a longer trek through city streets.",
    "3–12 Blocks – a cross‑town journey.",
    "4–20 Blocks – a lengthy trip requiring public transit.",
    "Half‑Day Drive – a road trip to a neighbouring city.",
    "1–4 Day Drive – a journey across multiple states or regions.",
    "One Week’s Drive – roughly a week of cross‑country travel.",
    "Neighbouring Town – a trip to the next town over.",
    "Neighbouring State – crossing state lines to a new jurisdiction.",
    "Neighbouring Country – travelling across national borders.",
]

MODERN_RANDOM_ENCOUNTERS: List[str] = [
    "Street Gang – A group of thugs harasses passers‑by and demands cash.",
    "Lost Tourist – Someone asks for directions and spills gossip inadvertently.",
    "Car Chase – Vehicles tear through the streets causing chaos.",
    "Severe Weather – A sudden storm or heatwave disrupts movement.",
    "Protest – A demonstration blocks roads and invites confrontation.",
    "Pickpocket – A thief targets the heroes’ wallets or phones.",
    "News Crew – Reporters and cameras swarm to cover a breaking story.",
    "Power Outage – Lights go out, causing confusion and opportunity for crime.",
    "Street Performer – An artist draws a crowd, which may hide an ulterior motive.",
    "Police Patrol – Officers question the party’s activities.",
    "Animal Encounter – A stray dog or raccoon follows the PCs.",
    "Building Fire – Smoke and flames erupt, drawing emergency services.",
]

MODERN_REWARDS: List[str] = [
    "A cash bonus or electronic payment.",
    "A high‑end gadget or piece of equipment.",
    "Positive media coverage or social media boost.",
    "A new car or upgraded vehicle.",
    "A valuable piece of jewellery or artwork.",
    "Inside information or confidential files.",
    "An honorary title or public commendation.",
    "Top‑tier medical treatment or insurance.",
    "A customised weapon or security system.",
    "A loyal pet or trained working animal.",
    "A bundle of stock options or ownership shares.",
    "Continued patronage and future contracts.",
]

MODERN_PENALTIES: List[str] = [
    "Fines and legal penalties.",
    "Loss of driver’s licence or professional licence.",
    "Damage to reputation or social credit.",
    "Physical injury requiring hospital care.",
    "Police record or arrest warrant.",
    "A powerful enemy suing or retaliating.",
    "Higher insurance premiums or loss of insurance.",
    "A trusted contact cuts ties with the party.",
    "Vandalism or theft of the heroes’ property.",
    "A loved one is endangered or ostracised.",
    "Competitors claim the reward first.",
    "No direct penalty – only wasted time and expenses.",
]

MODERN_QUEST_ITEMS: List[str] = [
    "Encrypted flash drive containing incriminating evidence.",
    "Prototype smartphone loaded with cutting‑edge software.",
    "VIP access badge granting entry to secure locations.",
    "Bag of unmarked bills destined for a payoff.",
    "Blueprints of a skyscraper or industrial site.",
    "Hardcopy dossier detailing a criminal operation.",
    "Cultural artefact stolen from a museum.",
    "Signed contract needed to complete a deal.",
    "Tracking device used to monitor a target.",
    "Encrypted key card for a secret server room.",
    "Vial of a cutting‑edge experimental drug.",
    "Antique locket holding a vital photograph.",
]


def generate_modern_campaign() -> Dict[str, str]:
    """Generate a random modern campaign with detailed descriptions.

    Uses the same composition functions as other settings to provide
    extended narrative elements and ensure depth for each field.  This
    satisfies the requirement for longer entries built from multiple
    rolls.
    """
    campaign: Dict[str, str] = {}
    campaign["Starting Location"] = compose_detailed_starting("Modern")
    campaign["Quest"] = compose_detailed_quest("Modern")
    campaign["Quest Hook"] = compose_detailed_hook("Modern")
    campaign["Quest Giver"] = compose_detailed_giver("Modern")
    campaign["Key NPC"] = compose_detailed_npc("Modern")
    campaign["Region"] = compose_detailed_region("Modern")
    campaign["Travel Distance"] = compose_detailed_distance("Modern")
    campaign["Random Encounter"] = compose_detailed_encounter("Modern")
    campaign["Reward"] = compose_detailed_reward("Modern")
    campaign["Penalty"] = compose_detailed_penalty("Modern")
    campaign["Quest Item"] = compose_detailed_item("Modern")
    return campaign


# Post‑apocalyptic tables
PA_STARTING_LOCATIONS: List[str] = [
    "Ruined Diner – Survivors meet in a crumbling pre‑war restaurant while trading stories.",
    "Jury‑Rigged Jail – The PCs are locked in a makeshift holding cell by a local militia.",
    "Barter Town – A settlement’s market attracts wanderers who overhear a lucrative lead.",
    "Community Bunker – Residents of the same vault or bunker gather to discuss a problem.",
    "Shared Refuge – All characters seek shelter in the same collapsed tunnel during a radstorm.",
    "Wanted Board – A board outside a sheriff’s office lists bounties and salvage contracts.",
    "Forced Service – A raider boss conscripts strangers to pay off made‑up debts.",
    "Celebration Gone Wrong – A harvest festival in a settlement turns deadly after a mutant attack.",
    "Trading Post Robbery – A group of raiders assaults a caravan, forcing strangers to fight together.",
    "Caravan Trek – Travellers share a long, dusty road on a brahmin caravan.",
    "Funeral Pyre – Survivors hold a funeral for someone lost to the wastes.",
    "Shelter Collapse – After the roof caves in, a handful of survivors are trapped together.",
]

PA_QUEST_TEMPLATES: List[str] = [
    "Hunt Raiders – Track down and eliminate a band of raiders terrorising a settlement.",
    "Clear Mutants – Drive feral ghouls or radscorpions out of a community’s perimeter.",
    "Defuse Warhead – Safely disarm an unexploded bomb left from the old war.",
    "Scavenge Parts – Collect usable components from a ruined factory or vehicle yard.",
    "Assassinate Warlord – Take out a tyrannical raider leader before they grow stronger.",
    "Escort Caravan – Protect a merchant caravan through dangerous territories.",
    "Guard Pilgrim – Escort a travelling preacher or wise old ghoul to a distant shrine.",
    "Deliver Water – Transport a shipment of clean water to a parched settlement.",
    "Rescue Captives – Free settlers captured by mutants or raiders.",
    "Gather Medicine – Search hospitals and clinics for chems and first aid supplies.",
    "Stop Cult – Prevent a doomsday cult from activating a toxic device.",
    "Explore Ruin – Map and loot an unexplored pre‑war vault or military base.",
]

PA_QUEST_HOOKS: List[str] = [
    "Grizzled Trader – A merchant promises payment in caps and supplies for a dangerous job.",
    "Off‑Record – The settlement’s overseer quietly requests help without telling the council.",
    "Defending Home – The quest defends the PC’s own shelter or community.",
    "Personal Vendetta – A raider or beast hurt someone close to the PCs.",
    "Event Threat – The task coincides with the settlement’s scarce celebration of life.",
    "Cryptic Broadcast – A radio signal repeats coordinates and a plea for help.",
    "Prophetic Vision – A tribal shaman’s dream warns of impending doom.",
    "Accidental Find – The PCs find a holotape or note revealing a secret plan.",
    "Revenge – Someone seeks justice against a warlord or corrupt overseer.",
    "Help the Weak – Helpless settlers beg the PCs for aid against raiders or famine.",
    "Mandatory – A powerful faction issues orders under threat of exile.",
    "Tribal Duty – A tribe or clan to which a PC belongs needs this task done.",
]

PA_QUEST_GIVERS: List[str] = [
    "Settlement Leader – The head of a town, offering food and shelter for success.",
    "Sheriff – A law‑keeper who can jail or pardon at will.",
    "Wandering Trader – A merchant with caravans of goods and information.",
    "Shaman – A spiritual advisor providing guidance and occasional healing.",
    "Warlord – A raider leader willing to hire mercenaries for dirty work.",
    "Quartermaster – A supplier who doles out rations and ammo for favours.",
    "Mechanic – A tinker who needs rare parts to repair vital machinery.",
    "Caravan Boss – A seasoned trader who hires escorts and scouts.",
    "Veteran Ranger – An experienced wasteland ranger offering training and tips.",
    "Scavenger – A wastelander needing help retrieving loot from a ruin.",
    "Doctor – A medic who pays in healing supplies for assistance.",
    "Mysterious Voice – An unknown person on the radio offering rewards for tasks.",
]

PA_NPC_QUICK_PICK: List[str] = [
    "Scavenger – A scrappy survivor adept at looting and bargaining.",
    "Vault Dweller – A naive newcomer from a sheltered bunker exploring the wastes.",
    "Trader – A merchant who trades caps, ammo and information.",
    "Raider – A violent bandit looking to extort or pillage.",
    "Ranger – A guardian of the wastes skilled with rifles and survival.",
    "Mechanic – An engineer who can jury‑rig and repair machinery.",
    "Medic – A doctor making do with improvised tools and chems.",
    "Ghoul – A radiation‑scarred wanderer with long memory and resilience.",
    "Super Mutant – A hulking brute torn between violence and loyalty.",
    "Pre‑War Robot – An AI‑driven machine still performing its original duties.",
    "Chem Cook – A drug manufacturer knowledgeable in chemistry and barter.",
    "Tribal Warrior – A primitive fighter using bows, spears or cobbled firearms.",
]

PA_TERRAIN_TYPES: List[str] = [
    "Ruined City – Crumbling skyscrapers, collapsed highways and hidden dangers.",
    "Irradiated Desert – Endless dunes dotted with glowing craters and glass.",
    "Blasted Forest – Charred trees and mutated wildlife.",
    "Rad‑Swamp – Toxic bogs teeming with mirelurks and radcrocs.",
    "Vault – Subterranean bunkers filled with pre‑war tech and secrets.",
    "Makeshift Settlement – Ramshackle huts built from scrap and ruins.",
    "Underground Tunnels – Sewers, metro lines and service ducts.",
    "Warlord Camp – Fortified raider encampments built from scrap metal.",
    "Radiation Zone – Areas where Geiger counters click furiously and dangers abound.",
    "Oil Fields – Rusting rigs, pools of sludge and flammable fumes.",
    "Mountain Caves – Natural shelters inhabited by creatures and outcasts.",
]

PA_OVERLAND_DISTANCES: List[str] = [
    "Adjacent Area – just down the road or over the hill.",
    "Half‑Day Walk – up to half a day on foot.",
    "Full‑Day Walk – a day’s journey by foot or brahmin caravan.",
    "Two‑Day Hike – a couple of days trekking through dangerous terrain.",
    "Three‑Day Trek – days of travel across mutant‑infested land.",
    "Weeklong Journey – a week travelling with pack animals or on foot.",
    "One‑Day Ride – a day by makeshift vehicle if fuel can be found.",
    "1–4 Day Ride – one to four days in a rusted but working truck.",
    "One‑Week Ride – roughly a week in a repaired pre‑war vehicle.",
    "Neighbouring Settlement – a trip to the next town or trading post.",
    "Neighbouring Region – cross into territory held by another faction.",
    "Far‑Off Ruin – travel to a distant city or vault across the wastes.",
]

PA_RANDOM_ENCOUNTERS: List[str] = [
    "Raider Ambush – Marauders spring from cover to demand caps or blood.",
    "Mutant Beast – A radscorpion, yao guai or deathclaw stalks the party.",
    "Radiation Storm – A fierce radstorm forces the party to seek shelter or take damage.",
    "Broken Bridge – A collapsed bridge forces a detour across hazardous terrain.",
    "Lost Child – An orphaned child begs for help finding their family.",
    "Booby Trap – A rigged explosive or tripwire threatens unwary travellers.",
    "Crash Site – A pre‑war vertibird or caravan lies wrecked and ripe for salvage.",
    "Supply Drop – A parachute‑borne crate contains random goods but attracts attention.",
    "Rival Scavengers – Another group competes for the same loot.",
    "Purifier Malfunction – A water purifier or generator fails, requiring repair.",
    "Swarm of Vermin – A horde of molerats or radroaches bursts from the ground.",
    "Old World Robot – A malfunctioning robot mistakes the PCs for its long‑dead crew.",
]

PA_REWARDS: List[str] = [
    "A stash of bottle caps and precious ammunition.",
    "Working pre‑war tech like a pip‑boy or laser pistol.",
    "Favour with a local settlement, granting supplies and shelter.",
    "Ownership of a brahmin or makeshift vehicle.",
    "A cache of purified water and preserved food.",
    "Blueprints for crafting weapons or armour.",
    "An honorary title or position in the settlement council.",
    "Rare chems or medical supplies.",
    "A well‑maintained firearm or set of armour.",
    "A loyal animal companion such as a dog or molerat.",
    "A toolkit with spare parts and repair materials.",
    "A map marking untouched ruins or supply caches.",
]

PA_PENALTIES: List[str] = [
    "Loss of caps and valuable goods.",
    "Radiation sickness requiring immediate treatment.",
    "Exile from the nearest settlement.",
    "Broken or stolen weapons and gear.",
    "Increased bounty from raider gangs.",
    "Perpetual harassment by mutated creatures.",
    "A powerful faction declares the PCs enemies on sight.",
    "A companion NPC is captured or killed.",
    "Disease outbreak in the PCs’ home due to failure.",
    "Loss of vehicle or pack animals.",
    "Rival scavengers claim the reward first.",
    "No immediate penalty – only wasted time and resources.",
]

PA_QUEST_ITEMS: List[str] = [
    "Water purifier filter that can clean radiation from water.",
    "Prototype fusion core needed to power a settlement.",
    "Pre‑war holotape with encrypted coordinates.",
    "Box of anti‑rad medicine for a sick community.",
    "Personal journal revealing a stash location.",
    "Set of functioning power armour servos.",
    "A rare intact book of knowledge from before the bombs.",
    "Vault keycard granting access to a sealed bunker.",
    "Capsule of pre‑war seeds crucial for farming.",
    "Weapon schematics for a powerful energy rifle.",
    "A vial of FEV (Forced Evolutionary Virus) sample.",
    "A mysterious statue rumoured to bring luck to settlements.",
]


def generate_postapoc_campaign() -> Dict[str, str]:
    """Generate a random post‑apocalyptic campaign with richly detailed entries.

    Leverages the same multi‑roll composition functions to craft
    descriptive paragraphs, blending seeds from the source tables with
    additional context and flavour unique to the wasteland.
    """
    campaign: Dict[str, str] = {}
    campaign["Starting Location"] = compose_detailed_starting("Post‑Apocalyptic")
    campaign["Quest"] = compose_detailed_quest("Post‑Apocalyptic")
    campaign["Quest Hook"] = compose_detailed_hook("Post‑Apocalyptic")
    campaign["Quest Giver"] = compose_detailed_giver("Post‑Apocalyptic")
    campaign["Key NPC"] = compose_detailed_npc("Post‑Apocalyptic")
    campaign["Region"] = compose_detailed_region("Post‑Apocalyptic")
    campaign["Travel Distance"] = compose_detailed_distance("Post‑Apocalyptic")
    campaign["Random Encounter"] = compose_detailed_encounter("Post‑Apocalyptic")
    campaign["Reward"] = compose_detailed_reward("Post‑Apocalyptic")
    campaign["Penalty"] = compose_detailed_penalty("Post‑Apocalyptic")
    campaign["Quest Item"] = compose_detailed_item("Post‑Apocalyptic")
    return campaign


# Mapping from settings to generator functions
GENERATOR_FUNCTIONS = {
    "Fantasy": generate_fantasy_campaign,
    "Sci‑Fi": generate_scifi_campaign,
    "Modern": generate_modern_campaign,
    "Post‑Apocalyptic": generate_postapoc_campaign,
}


# ---------------------------------------------------------------------------
# Dynamic campaign content generation
#
# The following helper functions generate random entries for each campaign
# category.  They combine base seeds drawn from the FlexTale Campaign
# Generator with dynamically generated combinations of adjectives, nouns,
# verbs and other parts of speech.  This ensures that each table has a
# sample space of at least 250 unique possibilities per setting, as
# requested.  Seeds from the PDF—such as tavern, jail, dinner party and
# quest item categories like signet ring or artwork【508372632574507†L1548-L1589】【508372632574507†L1988-L2052】—are included alongside
# generated combinations to preserve the flavour of the original tables.

import math

# Common word lists used across categories
COMMON_ADJECTIVES = [
    "Abandoned", "Ancient", "Bustling", "Quiet", "Haunted", "Sacred", "Hidden",
    "Crumbling", "Shrouded", "Stormy", "Lush", "Frozen", "Burning", "Enchanted",
    "Secluded", "Radiant", "Misty", "Forgotten", "Mythic", "Seaside",
]

SCI_ADJECTIVES = [
    "Futuristic", "Neon‑lit", "Cybernetic", "Quantum", "Alien", "Sleek",
    "Decaying", "Artificial", "Sterile", "Orbital",
]

MODERN_ADJECTIVES = [
    "Urban", "Suburban", "Rural", "Industrial", "Downtown", "Underground",
    "Corporate", "Gentrified", "Historic", "Trendy",
]

POST_APOC_ADJECTIVES = [
    "Ruined", "Irradiated", "Blasted", "Rusted", "Makeshift", "Dusty",
    "Scarred", "Toxic", "Collapsed", "Forgotten",
]

# Starting location nouns per setting
STARTING_NOUNS = {
    "Fantasy": [
        "Tavern", "Forest", "Temple", "Dungeon", "Castle", "Marketplace",
        "Caravan", "Crypt", "Library", "Shrine", "Arena", "Bridge", "Village",
        "Mountain", "Riverbank", "Meadow", "Monastery", "Harbour", "Inn",
    ],
    "Sci‑Fi": [
        "Space Station", "Cruiser", "Nebula", "Derelict Ship", "Research Lab",
        "Colony", "Asteroid Belt", "Starport", "Observatory", "Planet", "Arcology",
        "Cybernetics Lab", "Quantum Reactor", "Docking Bay", "Freighter", "Orbital",
        "Holo‑arcade", "Habitat Ring", "Mining Outpost",
    ],
    "Modern": [
        "Coffee Shop", "Police Station", "Boardroom", "Subway Station", "Hospital",
        "Warehouse", "Nightclub", "Office Building", "Mall", "University Campus",
        "Airport Terminal", "Neighbourhood Block", "Park", "Courtroom", "Rooftop",
        "Train Station", "Apartment Complex", "Downtown Alley",
    ],
    "Post‑Apocalyptic": [
        "Ruined Diner", "Vault", "Shelter", "Bunker", "Settlement", "Cave",
        "Factory", "Outpost", "Camp", "Rubble Pile", "Bridge", "Subway Tunnel",
        "Radiation Zone", "Highway Overpass", "Oil Field", "Cistern", "Scrapyard",
        "Deserted Farm", "Abandoned School",
    ],
}

# Quest verbs and objects (shared across settings)
QUEST_VERBS = [
    "Investigate", "Rescue", "Escort", "Defend", "Deliver", "Smuggle", "Defuse",
    "Hunt", "Steal", "Collect", "Protect", "Infiltrate", "Hack", "Acquire",
    "Sabotage", "Neutralise", "Guard", "Discover", "Retrieve", "Chart",
]

QUEST_OBJECTS = [
    "artifact", "hostage", "caravan", "outpost", "cargo", "data chip",
    "engine core", "reactor", "VIP", "settlement", "prototype", "virus sample",
    "survivor", "device", "relic", "treasure", "encrypted file", "weapon prototype",
    "power cell", "ancient tome",
]

# Hook reasons and contexts
HOOK_REASONS = [
    "Wealth", "Revenge", "Honor", "Duty", "Fame", "Love", "Fear",
    "Prophecy", "Debt", "Survival", "Curiosity", "Power", "Justice",
    "Secrets", "Family",
]

HOOK_CONTEXTS = [
    "a family member", "a friend", "their village", "their city", "their guild",
    "their crew", "their kingdom", "their sector", "their corporation", "their faction",
    "their tribe", "their settlement", "their planet", "their bunker", "their ship",
]

# Quest giver roles and adjectives
GIVER_ROLES = [
    "Mayor", "Captain", "Noble", "Merchant", "Priest", "Guildmaster", "CEO",
    "Admiral", "Shaman", "Mechanic", "Detective", "Professor", "Warlord", "Ranger",
    "Trader", "Spy", "Engineer", "Botanist", "Scientist", "Smuggler", "Commander",
]

GIVER_ADJECTIVES = [
    "Mysterious", "Grizzled", "Young", "Elderly", "Cunning", "Kindly", "Ambitious",
    "Desperate", "Ruthless", "Eccentric", "Stoic", "Charming", "Enigmatic",
    "Wealthy", "Charismatic",
]

# NPC roles and adjectives
NPC_ROLES = [
    "Thief", "Warrior", "Mage", "Bard", "Ranger", "Cleric", "Druid", "Barbarian",
    "Paladin", "Assassin", "Wizard", "Scholar", "Engineer", "Medic", "Pilot",
    "Navigator", "Spy", "Sailor", "Soldier", "Merchant", "Noble", "Alchemist",
    "Gunslinger", "Trader", "Drifter", "Hacker", "Android", "Rogue", "Enforcer",
]

NPC_ADJECTIVES = [
    "Shady", "Brave", "Witty", "Stoic", "Greedy", "Loyal", "Cunning", "Foolish",
    "Cursed", "Curious", "Nervous", "Brash", "Serene", "Haunted", "Charming",
    "Grizzled", "Eloquent", "Hot‑headed", "Reserved", "Mystical", "Savvy",
]

# Region features
REGION_FEATURES = [
    "Forest", "Desert", "Mountain", "Jungle", "Swamp", "City", "Village",
    "Cave", "Sea", "Coast", "Island", "River", "Lake", "Space Station",
    "Asteroid Field", "Nebula", "Tundra", "Wasteland", "Plain", "Savanna",
    "Moon", "Volcano", "Ruins", "Underwater", "Temple", "Market", "Valley",
]

REGION_ADJECTIVES = [
    "Ancient", "Shrouded", "Frozen", "Burning", "Haunted", "Mystic", "Lost",
    "Remote", "Crystalline", "Blighted", "Radiant", "Overgrown", "Flooded",
    "Ravaged", "Glittering", "Foggy", "Vast", "Enchanted", "Dusty", "Icy",
]

# Encounter hazards and actions
ENCOUNTER_HAZARDS = [
    "bandits", "wolves", "zombies", "robots", "pirates", "raiders", "guards",
    "thugs", "wild animals", "ghosts", "mutants", "aliens", "cyborgs", "soldiers",
    "bugs", "storms", "golems", "dragons", "goblins", "demons", "spirits",
]

ENCOUNTER_ACTIONS = [
    "ambush", "attack", "harass", "offer aid", "ask for help", "challenge to a duel",
    "set a trap", "attempt to steal", "warn the party", "join forces", "follow suspiciously",
    "demand tribute", "block the path", "stalk from afar", "spread rumours", "seek shelter with",
]

# Reward adjectives and items
REWARD_ADJECTIVES = [
    "large", "small", "ancient", "rare", "unique", "valuable", "mysterious",
    "cursed", "sacred", "encrypted", "long‑lost", "gleaming", "priceless",
    "legendary", "ornate", "simple", "magical", "technological", "bio‑engineered",
]

REWARD_ITEMS = [
    "treasure chest", "artifact", "land deed", "magical weapon", "favour",
    "map", "spellbook", "vehicle", "title", "technology", "implant", "object",
    "relic", "secret", "clue", "heirloom", "potion", "dragon egg", "cyberdeck",
    "supply crate", "medicine kit", "engine blueprint", "food ration", "credit chip",
]

# Penalty adjectives and consequences
PENALTY_ADJECTIVES = [
    "heavy", "severe", "minor", "unexpected", "dire", "costly", "public",
    "hidden", "personal", "deadly", "humiliating", "mysterious", "legal",
    "financial", "social", "physical", "spiritual",
]

PENALTY_CONSEQUENCES = [
    "fine", "injury", "loss of respect", "exile", "curse", "enemy attack",
    "imprisonment", "arrest", "betrayal", "broken gear", "bad reputation",
    "nightmare", "disease", "quest sabotage", "social scandal", "confiscation",
    "banishment", "vendetta", "missing companion", "equipment failure",
]

# Quest item adjectives and objects
ITEM_ADJECTIVES = [
    "ancient", "encrypted", "cursed", "prototype", "stolen", "sacred", "missing",
    "valuable", "biometric", "sealed", "mysterious", "quantum", "alien", "pristine",
    "shattered", "frozen", "radiant", "toxic", "volatile",
]

ITEM_OBJECTS = [
    "amulet", "data chip", "sword", "artifact", "ring", "key", "scroll", "map",
    "book", "core", "fragment", "power cell", "potion", "gem", "serum", "idol",
    "tablet", "relic", "statue", "cube", "sample", "device", "chipset", "doll",
]


def generate_starting_location(setting: str) -> str:
    """Generate a starting location string for the given setting."""
    # Use seeds from the PDF occasionally
    seeds_map = {
        "Fantasy": FANTASY_STARTING_LOCATIONS,
        "Sci‑Fi": SCI_STARTING_LOCATIONS,
        "Modern": MODERN_STARTING_LOCATIONS,
        "Post‑Apocalyptic": PA_STARTING_LOCATIONS,
    }
    # 20% chance to return a seed directly
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    # Otherwise construct a new location
    nouns = STARTING_NOUNS[setting]
    # Choose adjectives depending on setting
    if setting == "Sci‑Fi":
        adjectives = COMMON_ADJECTIVES + SCI_ADJECTIVES
    elif setting == "Modern":
        adjectives = COMMON_ADJECTIVES + MODERN_ADJECTIVES
    elif setting == "Post‑Apocalyptic":
        adjectives = COMMON_ADJECTIVES + POST_APOC_ADJECTIVES
    else:
        adjectives = COMMON_ADJECTIVES
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    return f"{adj} {noun} – The party meets at this {adj.lower()} {noun.lower()} to begin their adventure."


# Functions to compose detailed entries by combining multiple random rolls

def compose_detailed_starting(setting: str) -> str:
    """Compose a longer starting location description using multiple random rolls.

    This function stitches together several generated fragments to build a
    multi‑sentence paragraph.  It begins with a seed or constructed
    starting location, mentions at least one nearby region, introduces
    two NPCs or hazards, and hints at an emerging rumour or quest item.
    """
    primary = generate_starting_location(setting)
    region_desc = generate_region(setting)
    region_name = region_desc.split(" – ")[0]
    npc_desc = generate_npc(setting)
    second_npc_desc = generate_npc(setting)
    encounter_desc = generate_random_encounter(setting)
    second_encounter = generate_random_encounter(setting)
    item_hint = generate_quest_item(setting)
    hook_hint = generate_quest_hook(setting)
    return (
        f"{primary} This hub abuts a {region_name.lower()} where dangers and opportunities abound. "
        f"During introductions, the party crosses paths with {npc_desc.lower()} and {second_npc_desc.lower()}. "
        f"Soon after, {encounter_desc.lower()}, followed by {second_encounter.lower()}. "
        f"Rumours circulate about {item_hint.lower()}, while whispers of {hook_hint.lower()} beckon them onward."
    )


def compose_detailed_quest(setting: str) -> str:
    """Compose a longer quest description by combining multiple quests and hooks.

    A primary quest is joined by two side objectives, and multiple
    motivations are referenced to weave a complex storyline.  This
    ensures that the adventure feels layered and detailed.
    """
    main_quest = generate_quest_template(setting)
    secondary_quest = generate_quest_template(setting)
    tertiary_quest = generate_quest_template(setting)
    hook1 = generate_quest_hook(setting)
    hook2 = generate_quest_hook(setting)
    return (
        f"{main_quest} In addition, the heroes must {secondary_quest.split(' – ')[0].lower()} and {tertiary_quest.split(' – ')[0].lower()}. "
        f"Motivations stem from {hook1.lower()} and {hook2.lower()}."
    )


def compose_detailed_hook(setting: str) -> str:
    """Compose a longer quest hook by combining multiple reasons and contexts.

    This merges several hooks into a single narrative, offering
    overlapping incentives or pressures that drive the party towards
    action.
    """
    first_hook = generate_quest_hook(setting)
    second_hook = generate_quest_hook(setting)
    third_hook = generate_quest_hook(setting)
    return (
        f"{first_hook} Additionally, {second_hook.lower()}, and moreover, {third_hook.lower()}."
    )


def compose_detailed_giver(setting: str) -> str:
    """Compose a longer quest giver description.

    The quest giver is fleshed out by introducing additional allies or
    rivals and by foreshadowing both the rewards and the consequences
    associated with the mission.  A final hook ties their motives to
    the overarching plot.
    """
    main_giver = generate_quest_giver(setting)
    secondary_giver = generate_quest_giver(setting)
    tertiary_giver = generate_quest_giver(setting)
    reward_hint = generate_reward(setting)
    penalty_hint = generate_penalty(setting)
    hook = generate_quest_hook(setting)
    return (
        f"{main_giver} They are accompanied by {secondary_giver.lower()} and shadowed by {tertiary_giver.lower()}. "
        f"They promise {reward_hint.lower()} but warn that failure may result in {penalty_hint.lower()}. "
        f"Compellingly, their plea is driven by {hook.lower()}"
    )


def compose_detailed_npc(setting: str) -> str:
    """Compose a longer NPC description with secrets or motives.

    Two NPCs are described in detail, with hidden identities, alliances
    and secret motivations.  Additional hooks hint at why they are
    connected to the heroes.
    """
    npc_main = generate_npc(setting)
    npc_secondary = generate_npc(setting)
    npc_tertiary = generate_npc(setting)
    secret_hook = generate_quest_hook(setting)
    second_secret = generate_quest_hook(setting)
    return (
        f"{npc_main} They conceal the identity of {npc_secondary.lower()} and secretly report to {npc_tertiary.lower()}. "
        f"Their allegiance to the party stems from {secret_hook.lower()}, yet they are torn by {second_secret.lower()}"
    )


def compose_detailed_region(setting: str) -> str:
    """Compose a longer region description including hazards.

    This function describes multiple adjacent regions, their unique
    qualities and hazards, and sometimes hints at secrets or rewards
    buried within.
    """
    region_main = generate_region(setting)
    region_secondary = generate_region(setting)
    region_tertiary = generate_region(setting)
    encounter_desc = generate_random_encounter(setting)
    second_encounter = generate_random_encounter(setting)
    item_hint = generate_quest_item(setting)
    return (
        f"{region_main} Beyond it lies {region_secondary.lower()} and then {region_tertiary.lower()}. "
        f"Travellers often report that {encounter_desc.lower()} and later {second_encounter.lower()}. "
        f"Hidden somewhere here is {item_hint.lower()}."
    )


def compose_detailed_distance(setting: str) -> str:
    """Compose a longer travel distance with obstacles.

    Describes the primary journey and a secondary leg of travel while
    mentioning terrain and potential hazards.  This builds a sense of
    the arduousness of the trip.
    """
    distance_main = generate_distance(setting)
    distance_secondary = generate_distance(setting)
    distance_tertiary = generate_distance(setting)
    region_desc = generate_region(setting)
    encounter_desc = generate_random_encounter(setting)
    return (
        f"{distance_main} Expect another {distance_secondary.lower()} and then {distance_tertiary.lower()} after passing through a {region_desc.split(' – ')[0].lower()}. "
        f"Along the way, {encounter_desc.lower()} may slow progress."
    )


def compose_detailed_encounter(setting: str) -> str:
    """Compose a longer encounter description combining multiple hazards.

    Two or more random encounters are chained together to create a
    challenging and varied sequence of events.
    """
    encounter1 = generate_random_encounter(setting)
    encounter2 = generate_random_encounter(setting)
    encounter3 = generate_random_encounter(setting)
    return (
        f"{encounter1} Shortly afterwards, {encounter2.lower()}, and finally, {encounter3.lower()}"
    )


def compose_detailed_reward(setting: str) -> str:
    """Compose a longer reward description combining tangible and intangible prizes.

    A trio of rewards is described, including a special quest item and
    hints of bonus advantages such as knowledge or favours.
    """
    reward1 = generate_reward(setting)
    reward2 = generate_reward(setting)
    reward3 = generate_reward(setting)
    quest_item = generate_quest_item(setting)
    hook = generate_quest_hook(setting)
    return (
        f"{reward1} In addition, {reward2.lower()} awaits, and {reward3.lower()} could also be earned. "
        f"A special prize, {quest_item.lower()}, may also be granted. "
        f"Moreover, {hook.lower()} might provide further boons."
    )


def compose_detailed_penalty(setting: str) -> str:
    """Compose a longer penalty description combining multiple negative outcomes.

    Multiple penalties are chained together, with additional hazards and
    hooks hinting at the reasons for the failures.  This makes the
    consequences feel weighty and narrative.
    """
    penalty1 = generate_penalty(setting)
    penalty2 = generate_penalty(setting)
    penalty3 = generate_penalty(setting)
    encounter_desc = generate_random_encounter(setting)
    hook = generate_quest_hook(setting)
    return (
        f"{penalty1} Further, {penalty2.lower()}, and moreover, {penalty3.lower()}. "
        f"Complications may arise when {encounter_desc.lower()}, especially if {hook.lower()}"
    )


def compose_detailed_item(setting: str) -> str:
    """Compose a longer quest item description combining different properties.

    Multiple unique items are described together, along with hints of
    rewards and penalties associated with their possession.  This
    encourages the party to weigh the risks and benefits.
    """
    item1 = generate_quest_item(setting)
    item2 = generate_quest_item(setting)
    item3 = generate_quest_item(setting)
    reward_hint = generate_reward(setting)
    penalty_hint = generate_penalty(setting)
    return (
        f"{item1} It is paired with {item2.lower()} and {item3.lower()}. "
        f"Legends say its finder will receive {reward_hint.lower()}, yet warn that {penalty_hint.lower()} may follow."
    )


def generate_quest_template(setting: str) -> str:
    """Generate a quest template string."""
    # Seeds from the book
    seeds_map = {
        "Fantasy": FANTASY_QUEST_TEMPLATES,
        "Sci‑Fi": SCI_QUEST_TEMPLATES,
        "Modern": MODERN_QUEST_TEMPLATES,
        "Post‑Apocalyptic": PA_QUEST_TEMPLATES,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    verb = random.choice(QUEST_VERBS)
    obj = random.choice(QUEST_OBJECTS)
    return f"{verb} {obj} – The heroes must {verb.lower()} the {obj}."


def generate_quest_hook(setting: str) -> str:
    """Generate a quest hook string."""
    seeds_map = {
        "Fantasy": FANTASY_QUEST_HOOKS,
        "Sci‑Fi": SCI_QUEST_HOOKS,
        "Modern": MODERN_QUEST_HOOKS,
        "Post‑Apocalyptic": PA_QUEST_HOOKS,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    reason = random.choice(HOOK_REASONS)
    context = random.choice(HOOK_CONTEXTS)
    return f"{reason} – They take on this mission for {reason.lower()} involving {context}."


def generate_quest_giver(setting: str) -> str:
    """Generate a quest giver description."""
    seeds_map = {
        "Fantasy": FANTASY_QUEST_GIVERS,
        "Sci‑Fi": SCI_QUEST_GIVERS,
        "Modern": MODERN_QUEST_GIVERS,
        "Post‑Apocalyptic": PA_QUEST_GIVERS,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(GIVER_ADJECTIVES)
    role = random.choice(GIVER_ROLES)
    return f"{adj} {role} – A {adj.lower()} {role.lower()} seeks assistance."


def generate_npc(setting: str) -> str:
    """Generate a key NPC description."""
    seeds_map = {
        "Fantasy": FANTASY_NPC_QUICK_PICK,
        "Sci‑Fi": SCI_NPC_QUICK_PICK,
        "Modern": MODERN_NPC_QUICK_PICK,
        "Post‑Apocalyptic": PA_NPC_QUICK_PICK,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(NPC_ADJECTIVES)
    role = random.choice(NPC_ROLES)
    return f"{adj} {role} – A {adj.lower()} {role.lower()} crosses your path."


def generate_region(setting: str) -> str:
    """Generate a region description."""
    seeds_map = {
        "Fantasy": FANTASY_TERRAIN_TYPES,
        "Sci‑Fi": SCI_TERRAIN_TYPES,
        "Modern": MODERN_TERRAIN_TYPES,
        "Post‑Apocalyptic": PA_TERRAIN_TYPES,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(REGION_ADJECTIVES)
    feature = random.choice(REGION_FEATURES)
    return f"{adj} {feature} – A {adj.lower()} {feature.lower()} with its own mysteries."


def generate_distance(setting: str) -> str:
    """Generate a travel distance string."""
    # If seeds exist, occasionally use them
    seeds_map = {
        "Fantasy": FANTASY_OVERLAND_DISTANCES,
        "Sci‑Fi": SCI_OVERLAND_DISTANCES,
        "Modern": MODERN_OVERLAND_DISTANCES,
        "Post‑Apocalyptic": PA_OVERLAND_DISTANCES,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    # Define units per setting
    if setting == "Sci‑Fi":
        units = ["hexes", "sectors", "parsecs", "light years", "galactic arms", "jumps"]
        num = random.randint(1, 20)
        return f"{num} {random.choice(units)} – A journey of {num} {units[0]} across the stars."
    elif setting == "Modern":
        units = ["blocks", "miles", "days' drive", "hours' flight", "states", "countries"]
        num = random.randint(1, 50)
        return f"{num} {random.choice(units)} – Approximately {num} {units[0]} from here."
    elif setting == "Post‑Apocalyptic":
        units = ["days walk", "days ride", "miles", "regions", "sectors"]
        num = random.randint(1, 30)
        return f"{num} {random.choice(units)} – A hazardous {num} {units[0]} through the wastes."
    else:  # Fantasy
        units = ["hexes", "days", "weeks", "leagues", "spans", "journeys"]
        num = random.randint(1, 20)
        return f"{num} {random.choice(units)} – A trek of {num} {units[0]} across wild lands."


def generate_random_encounter(setting: str) -> str:
    """Generate a random encounter description."""
    seeds_map = {
        "Fantasy": FANTASY_RANDOM_ENCOUNTERS,
        "Sci‑Fi": SCI_RANDOM_ENCOUNTERS,
        "Modern": MODERN_RANDOM_ENCOUNTERS,
        "Post‑Apocalyptic": PA_RANDOM_ENCOUNTERS,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    hazard = random.choice(ENCOUNTER_HAZARDS)
    action = random.choice(ENCOUNTER_ACTIONS)
    return f"{hazard.capitalize()} {action} – The {hazard} {action}s the party along their journey."


def generate_reward(setting: str) -> str:
    """Generate a reward description."""
    seeds_map = {
        "Fantasy": FANTASY_REWARDS,
        "Sci‑Fi": SCI_REWARDS,
        "Modern": MODERN_REWARDS,
        "Post‑Apocalyptic": PA_REWARDS,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(REWARD_ADJECTIVES)
    item = random.choice(REWARD_ITEMS)
    return f"A {adj} {item}."


def generate_penalty(setting: str) -> str:
    """Generate a penalty description."""
    seeds_map = {
        "Fantasy": FANTASY_PENALTIES,
        "Sci‑Fi": SCI_PENALTIES,
        "Modern": MODERN_PENALTIES,
        "Post‑Apocalyptic": PA_PENALTIES,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(PENALTY_ADJECTIVES)
    consequence = random.choice(PENALTY_CONSEQUENCES)
    return f"A {adj} {consequence}."


def generate_quest_item(setting: str) -> str:
    """Generate a quest item description."""
    seeds_map = {
        "Fantasy": FANTASY_QUEST_ITEMS,
        "Sci‑Fi": SCI_QUEST_ITEMS,
        "Modern": MODERN_QUEST_ITEMS,
        "Post‑Apocalyptic": PA_QUEST_ITEMS,
    }
    if random.random() < 0.2:
        return random.choice(seeds_map[setting])
    adj = random.choice(ITEM_ADJECTIVES)
    obj = random.choice(ITEM_OBJECTS)
    return f"{adj.capitalize()} {obj}."


def export_to_docx(campaign: Dict[str, str], filename: str) -> None:
    """Create a DOCX file containing the campaign information with styled headings and text."""
    # Escape special XML characters
    def xml_escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&apos;")
            .replace('"', "&quot;")
        )

    # Build paragraphs with two runs: bold coloured heading and normal coloured description
    paragraphs = []
    for key, value in campaign.items():
        heading_run = f"<w:r><w:rPr><w:b/><w:color w:val='2C3E50'/><w:sz w:val='28'/></w:rPr><w:t>{xml_escape(key)}</w:t></w:r>"
        br = "<w:br/>"
        desc_run = f"<w:r><w:rPr><w:color w:val='34495E'/><w:sz w:val='24'/></w:rPr><w:t>{xml_escape(value)}</w:t></w:r>"
        # Add spacing after each paragraph
        paragraph = f"<w:p><w:pPr><w:spacing w:after='300'/></w:pPr>{heading_run}{br}{desc_run}</w:p>"
        paragraphs.append(paragraph)
    body_xml = "\n        ".join(paragraphs)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
        {body_xml}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="R1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    # Create the DOCX (a zip archive with specific files)
    with zipfile.ZipFile(filename, "w") as docx_zip:
        # Write content types
        docx_zip.writestr("[Content_Types].xml", content_types)
        # Write relationships
        docx_zip.writestr("_rels/.rels", rels_xml)
        # Write document
        docx_zip.writestr("word/document.xml", document_xml)


class CampaignGeneratorApp(tk.Tk):
    """Main application window for generating campaigns."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Scenario Generator")
        # Set a sensible default window size; allow resizing
        self.geometry("1920x1080")
        self.minsize(500, 500)
        # Primary background colour for a dark theme
        self.configure(bg="#2c3e50")
        # Use a ttk style for a modern appearance
        self.style = ttk.Style(self)
        # 'clam' theme provides good contrast
        self.style.theme_use("clam")
        # General typography for labels and buttons
        self.style.configure(
            "TLabel",
            background="#2c3e50",
            foreground="white",
            font=("Helvetica", 12),
        )
        # Buttons are styled with a slightly lighter background and white text
        self.style.configure(
            "TButton",
            font=("Helvetica", 12, "bold"),
            padding=6,
            foreground="white",
            background="#3498db",
        )
        # Menu buttons (used by OptionMenu) share similar styling
        self.style.configure(
            "TMenubutton",
            font=("Helvetica", 12),
            background="#34495e",
            foreground="white",
            padding=4,
        )
        # Selected setting variable
        self.setting_var = tk.StringVar(value="Fantasy")
        # Setup UI widgets
        self._create_widgets()
        # Placeholder for campaign data
        self.current_campaign: Dict[str, str] | None = None

    def _create_widgets(self) -> None:
        # Header label
        header = ttk.Label(
            self,
            text="Scenario Generator",
            font=("Helvetica", 20, "bold"),
            foreground="white",
            background="#2c3e50",
        )
        header.pack(pady=(15, 5))

        # Frame for controls
        top_frame = ttk.Frame(self, padding="10 10 10 10")
        top_frame.pack(fill="x")
        # Setting selection
        ttk.Label(top_frame, text="Select Setting:").pack(side="left")
        settings = list(GENERATOR_FUNCTIONS.keys())
        self.option_menu = ttk.OptionMenu(top_frame, self.setting_var, settings[0], *settings)
        self.option_menu.pack(side="left", padx=10)
        # Generate button
        generate_button = ttk.Button(
            top_frame,
            text="Generate",
            command=self.generate_campaign,
        )
        generate_button.pack(side="left", padx=10)
        # Export button
        self.export_button = ttk.Button(
            top_frame,
            text="Export to DOCX",
            command=self.export_campaign,
        )
        self.export_button.pack(side="left", padx=10)
        self.export_button.state(["disabled"])  # Disabled until campaign generated

        # Export to JSON button
        self.export_json_button = ttk.Button(
            top_frame,
            text="Export to JSON",
            command=self.export_campaign_json,
        )
        self.export_json_button.pack(side="left", padx=10)
        self.export_json_button.state(["disabled"])  # Disabled until campaign generated
        # Results display area using canvas and cards
        self.results_frame = ttk.Frame(self)
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        # Canvas for scrollable area
        self.canvas = tk.Canvas(
            self.results_frame,
            bg="#2c3e50",
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self.results_frame,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        # Frame inside canvas to hold cards
        self.cards_frame = tk.Frame(self.canvas, bg="#2c3e50")
        self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        # Configure resizing
        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

    def generate_campaign(self) -> None:
        """Generate and display a campaign for the selected setting."""
        setting = self.setting_var.get()
        try:
            generate_func = GENERATOR_FUNCTIONS[setting]
            campaign = generate_func()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate campaign: {e}")
            return
        self.current_campaign = campaign
        # Clear existing cards
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        # Create a card for each entry
        for key, value in campaign.items():
            card = tk.Frame(self.cards_frame, bg="#34495e", bd=1, relief="ridge")
            title_label = tk.Label(
                card,
                text=key,
                bg="#34495e",
                fg="#ecf0f1",
                font=("Helvetica", 14, "bold"),
            )
            desc_label = tk.Label(
                card,
                text=value,
                bg="#34495e",
                fg="#bdc3c7",
                wraplength=1700,
                justify="left",
                font=("Helvetica", 11),
            )
            title_label.pack(anchor="w", padx=8, pady=(4, 0))
            desc_label.pack(anchor="w", padx=8, pady=(0, 6))
            card.pack(fill="x", expand=True, padx=5, pady=5)
        # Enable export button
        self.export_button.state(["!disabled"])
        self.export_json_button.state(["!disabled"])

    def export_campaign(self) -> None:
        if not self.current_campaign:
            messagebox.showwarning("No Campaign", "Please generate a campaign first.")
            return
        # Ask user where to save the docx
        filename = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")],
            title="Save Campaign as DOCX",
            initialfile="campaign.docx",
        )
        if not filename:
            return  # Cancelled
        try:
            export_to_docx(self.current_campaign, filename)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export DOCX: {e}")
            return
        messagebox.showinfo("Export Successful", f"Campaign saved to {filename}")

    def export_campaign_json(self) -> None:
        """Export the current campaign to a JSON file using the provided template.

        The generated scenario is converted into a dictionary with fields
        Title, Summary, Secrets, Places and NPCs.  Summary and Secrets are
        stored as objects containing text and empty formatting lists to
        mirror the example template.  If the chosen file already exists
        and contains a JSON list, the scenario will be appended; otherwise
        a new list is created.
        """
        if not self.current_campaign:
            messagebox.showwarning("No Campaign", "Please generate a campaign first.")
            return
        # Ask user where to save the JSON
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Campaign as JSON",
            initialfile="campaign.json",
        )
        if not filename:
            return
        # Build scenario dictionary from current campaign
        campaign = self.current_campaign
        # Determine title: use the first part of the quest before a dash or period
        quest_text = campaign.get("Quest", "Adventure")
        # Extract text before the first dash or period
        title_candidate = quest_text.split("–")[0].split("- ")[0]
        title_candidate = title_candidate.strip()
        if not title_candidate:
            title_candidate = "Generated Adventure"
        # Compose summary: join starting location and quest
        summary_text = f"{campaign.get('Starting Location', '')} {campaign.get('Quest', '')}"
        # Compose secrets: use the penalty description as a secret
        secrets_text = campaign.get("Penalty", "")
        # Extract places: take the part of Starting Location and Region before the dash
        places = []
        start_loc = campaign.get("Starting Location", "")
        if "–" in start_loc:
            places.append(start_loc.split("–")[0].strip())
        region = campaign.get("Region", "")
        # Region may contain multiple segments separated by ' and then '
        region_parts = []
        if "–" in region:
            region_parts.append(region.split("–")[0].strip())
        # Also scan for ' and then ' or ' and '
        for sep in [" and then ", " and "]:
            if sep in region:
                for part in region.split(sep):
                    p = part.split(" – ")[0].strip()
                    if p and p not in region_parts:
                        region_parts.append(p)
        places.extend(region_parts)
        # Remove duplicates
        places = list(dict.fromkeys([p for p in places if p]))
        # Extract NPCs: take primary NPC and quest giver names before dash
        npcs = []
        for field in ["Key NPC", "Quest Giver"]:
            val = campaign.get(field, "")
            if "–" in val:
                name = val.split("–")[0].strip()
                if name:
                    npcs.append(name)
        npcs = list(dict.fromkeys(npcs))
        # Prepare nested formatting structure
        formatting_empty = {"bold": [], "italic": [], "underline": [], "left": [], "center": [], "right": []}
        scenario = {
            "Title": title_candidate,
            "Summary": {"text": summary_text, "formatting": formatting_empty.copy()},
            "Secrets": {"text": secrets_text, "formatting": formatting_empty.copy()},
            "Places": places,
            "NPCs": npcs,
        }
        # Read existing data if the file exists and contains JSON list
        try:
            with open(filename, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                scenarios = existing
            else:
                scenarios = []
        except Exception:
            scenarios = []
        scenarios.append(scenario)
        # Write back to file
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"scenarios": scenarios}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save JSON: {e}")
            return
        messagebox.showinfo("Export Successful", f"Campaign saved to {filename}")


def main() -> None:
    app = CampaignGeneratorApp()
    app.mainloop()


if __name__ == "__main__":
    main()